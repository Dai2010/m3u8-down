from __future__ import annotations

import asyncio
import re
from urllib.parse import quote, unquote

from aiohttp import ClientSession, web

from .bilibili import prepare_bilibili_request
from .filter import is_ad_segment
from .parser import Segment, parse_playlist, resolve_url


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

    async def start(self) -> None:
        if self._runner:
            return
        self._session = ClientSession(headers=self.headers)
        self._app = web.Application()
        self._app.router.add_get("/stream.m3u8", self._handle_stream)
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

    def get_stream_url(self, original_m3u8_url: str) -> str:
        return f"http://{self.host}:{self.port}/stream.m3u8?src={quote(original_m3u8_url, safe='')}"

    async def _handle_stream(self, request: web.Request) -> web.Response:
        source = request.query.get("src")
        if not source:
            raise web.HTTPBadRequest(text="missing src")
        source = unquote(source)
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

    async def _handle_ts(self, request: web.Request) -> web.StreamResponse:
        source = request.query.get("src")
        if not source:
            raise web.HTTPBadRequest(text="missing src")
        source = unquote(source)
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
