from __future__ import annotations

import asyncio
from urllib.parse import quote, unquote

from aiohttp import ClientSession, web

from .filter import filter_playlist, is_ad_segment
from .parser import Segment, parse_playlist, playlist_to_m3u8


class ProxyServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        headers: dict[str, str] | None = None,
        filter_keywords: list[str] | None = None,
        use_regex: bool = False,
    ):
        self.host = host
        self.port = port
        self.headers = headers or {}
        self.filter_keywords = filter_keywords or []
        self.use_regex = use_regex
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
        async with session.get(source) as response:
            response.raise_for_status()
            content = await response.text()

        playlist = parse_playlist(content, source)
        if playlist.is_master:
            return web.Response(text=self._proxy_master_playlist(playlist), content_type="application/vnd.apple.mpegurl")

        for segment in playlist.segments:
            if is_ad_segment(segment, self.filter_keywords, self.use_regex):
                self._ad_urls.add(segment.url)
        filtered = filter_playlist(playlist, self.filter_keywords, self.use_regex)
        proxied_segments = [self._proxied_segment(segment) for segment in filtered.segments]
        filtered = filtered.with_segments(proxied_segments)
        return web.Response(text=playlist_to_m3u8(filtered), content_type="application/vnd.apple.mpegurl")

    async def _handle_ts(self, request: web.Request) -> web.StreamResponse:
        source = request.query.get("src")
        if not source:
            raise web.HTTPBadRequest(text="missing src")
        source = unquote(source)
        if source in self._ad_urls:
            return web.Response(status=204)

        session = self._require_session()
        async with session.get(source) as upstream:
            upstream.raise_for_status()
            response = web.StreamResponse(status=upstream.status, headers={"Content-Type": upstream.headers.get("Content-Type", "video/MP2T")})
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(1024 * 256):
                await response.write(chunk)
            await response.write_eof()
            return response

    def _proxy_master_playlist(self, playlist) -> str:
        variants = []
        for variant in playlist.variants:
            variants.append(type(variant)(variant.bandwidth, variant.resolution, variant.codecs, self.get_stream_url(variant.url)))
        return playlist_to_m3u8(playlist.__class__(version=playlist.version, is_master=True, variants=variants))

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
