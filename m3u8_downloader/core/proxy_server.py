from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import quote
from xml.sax.saxutils import escape

from aiohttp import ClientError, ClientSession, web

from .bilibili import BilibiliTrack, prepare_bilibili_request
from .filter import is_ad_segment
from .parser import Segment, parse_playlist, resolve_url


@dataclass(frozen=True)
class _DashSource:
    video: BilibiliTrack
    audio: BilibiliTrack | None
    duration_ms: int


class ProxyServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        headers: dict[str, str] | None = None,
        filter_keywords: list[str] | None = None,
        use_regex: bool = False,
        bilibili_compat: bool = False,
    ):
        self.host = host
        self.port = port
        self.headers = headers or {}
        self.filter_keywords = filter_keywords or []
        self.use_regex = use_regex
        self.bilibili_compat = bilibili_compat
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._session: ClientSession | None = None
        self._ad_urls: set[str] = set()
        self._dash_sources: dict[str, _DashSource] = {}

    async def start(self) -> None:
        if self._runner:
            return
        self._session = ClientSession(headers=self.headers)
        self._app = web.Application()
        self._app.router.add_get("/stream.m3u8", self._handle_stream)
        self._app.router.add_get("/bilibili.mpd", self._handle_bilibili_mpd)
        self._app.router.add_get("/media", self._handle_media)
        self._app.router.add_get("/ts", self._handle_ts)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        sockets = getattr(self._site, "_server", None).sockets if getattr(self._site, "_server", None) else None
        if sockets:
            self.port = sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
        if self._session:
            await self._session.close()
        self._app = None
        self._runner = None
        self._site = None
        self._session = None
        self._ad_urls.clear()
        self._dash_sources.clear()

    def get_stream_url(self, original_m3u8_url: str) -> str:
        return f"http://{self.host}:{self.port}/stream.m3u8?src={quote(original_m3u8_url, safe='')}"

    def get_media_url(self, original_media_url: str) -> str:
        return f"http://{self.host}:{self.port}/media?src={quote(original_media_url, safe='')}"

    def get_bilibili_dash_url(
        self,
        video: BilibiliTrack,
        audio: BilibiliTrack | None = None,
        duration_ms: int = 0,
    ) -> str:
        source_id = f"{len(self._dash_sources):x}-{id(video):x}"
        self._dash_sources[source_id] = _DashSource(video, audio, max(0, int(duration_ms)))
        return f"http://{self.host}:{self.port}/bilibili.mpd?id={source_id}"

    async def _handle_stream(self, request: web.Request) -> web.Response:
        source = request.query.get("src")
        if not source:
            raise web.HTTPBadRequest(text="missing src")
        session = self._require_session()
        request_url, request_headers = prepare_bilibili_request(source, self.headers, self.bilibili_compat)
        async with session.get(request_url, headers=request_headers) as response:
            response.raise_for_status()
            content = await response.text()

        playlist = parse_playlist(content, request_url)
        if playlist.is_master:
            text = self._proxy_master_playlist(content, request_url)
        else:
            text = self._proxy_media_playlist(content, request_url, playlist.segments)
        return web.Response(text=text, content_type="application/vnd.apple.mpegurl")

    async def _handle_bilibili_mpd(self, request: web.Request) -> web.Response:
        source_id = request.query.get("id", "")
        source = self._dash_sources.get(source_id)
        if source is None:
            raise web.HTTPNotFound(text="unknown playback source")
        duration = ""
        if source.duration_ms:
            duration = f' mediaPresentationDuration="PT{source.duration_ms / 1000:.3f}S"'
        adaptations = [self._dash_adaptation(source_id, "video", source.video)]
        if source.audio is not None:
            adaptations.append(self._dash_adaptation(source_id, "audio", source.audio))
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" minBufferTime="PT1.5S"{duration}>'
            '<Period id="0">'
            + "".join(adaptations)
            + "</Period></MPD>"
        )
        return web.Response(text=content, content_type="application/dash+xml")

    async def _handle_media(self, request: web.Request) -> web.StreamResponse:
        sources = self._media_sources(request)
        if not sources:
            raise web.HTTPBadRequest(text="missing src")
        session = self._require_session()
        last_status = 502
        for source in sources:
            headers = dict(self.headers)
            for header_name in ("Range", "If-Range"):
                header_value = request.headers.get(header_name)
                if header_value:
                    headers[header_name] = header_value
            request_url, request_headers = prepare_bilibili_request(source, headers, self.bilibili_compat)
            try:
                async with session.get(request_url, headers=request_headers) as upstream:
                    if upstream.status >= 400:
                        last_status = upstream.status
                        continue
                    response_headers = {
                        name: upstream.headers[name]
                        for name in (
                            "Accept-Ranges",
                            "Cache-Control",
                            "Content-Length",
                            "Content-Range",
                            "Content-Type",
                            "ETag",
                            "Last-Modified",
                        )
                        if name in upstream.headers
                    }
                    response = web.StreamResponse(status=upstream.status, headers=response_headers)
                    await response.prepare(request)
                    try:
                        async for chunk in upstream.content.iter_chunked(1024 * 256):
                            await response.write(chunk)
                        await response.write_eof()
                    except (ConnectionResetError, asyncio.CancelledError):
                        raise
                    return response
            except ClientError:
                continue
        raise web.HTTPBadGateway(text=f"upstream media unavailable ({last_status})")

    async def _handle_ts(self, request: web.Request) -> web.StreamResponse:
        source = request.query.get("src")
        if not source:
            raise web.HTTPBadRequest(text="missing src")
        if source in self._ad_urls:
            return web.Response(status=204)

        session = self._require_session()
        request_url, request_headers = prepare_bilibili_request(source, self.headers, self.bilibili_compat)
        async with session.get(request_url, headers=request_headers) as upstream:
            upstream.raise_for_status()
            response = web.StreamResponse(status=upstream.status, headers={"Content-Type": upstream.headers.get("Content-Type", "video/MP2T")})
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(1024 * 256):
                await response.write(chunk)
            await response.write_eof()
            return response

    def _proxy_master_playlist(self, content: str, base_url: str) -> str:
        output: list[str] = []
        pending_variant = False
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if pending_variant and not line.startswith("#"):
                output.append(self.get_stream_url(resolve_url(base_url, line)))
                pending_variant = False
            elif line.startswith("#EXT-X-STREAM-INF:"):
                output.append(self._rewrite_tag_uris(line, base_url, stream=True))
                pending_variant = True
            else:
                output.append(self._rewrite_tag_uris(line, base_url, stream=True) if line.startswith("#") else line)
        return "\n".join(output) + "\n"

    def _proxy_media_playlist(self, content: str, base_url: str, segments: list[Segment]) -> str:
        output: list[str] = []
        pending_segment_tags: list[str] = []
        pending_title = ""
        segment_index = 0
        has_endlist = False

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "#EXTM3U":
                output.append(line)
            elif line == "#EXT-X-ENDLIST":
                has_endlist = True
            elif line.startswith("#EXTINF:"):
                pending_segment_tags.append(line)
                pending_title = line.partition(",")[2].strip()
            elif _is_segment_scoped_tag(line):
                pending_segment_tags.append(self._rewrite_tag_uris(line, base_url))
            elif line.startswith("#"):
                output.append(self._rewrite_tag_uris(line, base_url))
            else:
                absolute_url = resolve_url(base_url, line)
                segment = segments[segment_index] if segment_index < len(segments) else Segment(0, absolute_url, pending_title)
                segment_index += 1
                if is_ad_segment(segment, self.filter_keywords, self.use_regex):
                    self._ad_urls.add(segment.url)
                else:
                    output.extend(pending_segment_tags)
                    output.append(self._proxied_segment(segment).url)
                pending_segment_tags = []
                pending_title = ""

        if has_endlist:
            output.append("#EXT-X-ENDLIST")
        return "\n".join(output) + "\n"

    def _rewrite_tag_uris(self, line: str, base_url: str, stream: bool = False) -> str:
        def replace(match: re.Match[str]) -> str:
            target = resolve_url(base_url, match.group(1))
            if stream and line.startswith(("#EXT-X-I-FRAME-STREAM-INF", "#EXT-X-MEDIA")):
                target = self.get_stream_url(target)
            return f'URI="{target}"'

        return re.sub(r'URI="([^"]+)"', replace, line)

    def _proxied_segment(self, segment: Segment) -> Segment:
        url = f"http://{self.host}:{self.port}/ts?src={quote(segment.url, safe='')}"
        return Segment(segment.duration, url, segment.title, segment.discontinuity, segment.key)

    def _media_sources(self, request: web.Request) -> list[str]:
        source_id = request.query.get("dash", "")
        track_name = request.query.get("track", "")
        if source_id and track_name in {"video", "audio"}:
            dash_source = self._dash_sources.get(source_id)
            if dash_source is None:
                return []
            track = dash_source.video if track_name == "video" else dash_source.audio
            if track is None:
                return []
            return list(dict.fromkeys((track.url, *track.backup_urls)))
        source = request.query.get("src", "")
        return list(dict.fromkeys((source, *request.query.getall("backup", [])))) if source else []

    def _dash_adaptation(self, source_id: str, track_name: str, track: BilibiliTrack) -> str:
        if track_name == "video":
            attributes = [
                'contentType="video"',
                'mimeType="video/mp4"',
                f'codecs="{escape(track.codecs or _track_codec(track))}"',
            ]
            representation = [
                f'id="{track_name}"',
                f'bandwidth="{max(0, track.bandwidth)}"',
                f'width="{max(0, track.width)}"',
                f'height="{max(0, track.height)}"',
            ]
        else:
            attributes = ['contentType="audio"', 'mimeType="audio/mp4"']
            if track.language:
                attributes.append(f'lang="{escape(track.language)}"')
            representation = [
                f'id="{track_name}"',
                f'bandwidth="{max(0, track.bandwidth)}"',
            ]
        media_url = f"http://{self.host}:{self.port}/media?dash={quote(source_id, safe='')}&track={track_name}"
        return (
            f'<AdaptationSet {" ".join(attributes)}>'
            f'<Representation {" ".join(representation)}>'
            f'<BaseURL>{escape(media_url)}</BaseURL>'
            '</Representation></AdaptationSet>'
        )

    def _require_session(self) -> ClientSession:
        if not self._session:
            raise RuntimeError("proxy server is not started")
        return self._session


def run_proxy_until_stopped(server: ProxyServer, original_url: str) -> None:
    async def runner() -> None:
        await server.start()
        print(server.get_stream_url(original_url))
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await server.stop()

    asyncio.run(runner())


def _is_segment_scoped_tag(line: str) -> bool:
    return line == "#EXT-X-DISCONTINUITY" or line.startswith(
        (
            "#EXT-X-BYTERANGE",
            "#EXT-X-PROGRAM-DATE-TIME",
            "#EXT-X-DATERANGE",
            "#EXT-X-GAP",
            "#EXT-X-MAP",
            "#EXT-X-PART",
            "#EXT-X-PRELOAD-HINT",
        )
    )


def _track_codec(track: BilibiliTrack) -> str:
    if track.codec_id == 7:
        return "avc1"
    if track.codec_id == 12:
        return "hev1"
    if track.codec_id == 13:
        return "av01"
    return "mp4a.40.2" if track.track_type == "audio" else "mp4v.20.9"
