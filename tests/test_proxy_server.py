import asyncio

from aiohttp import web

from m3u8_downloader.core.proxy_server import ProxyServer


def test_proxy_stream_filters_ad_segments():
    async def run():
        async def playlist(request):
            return web.Response(
                text="""#EXTM3U
#EXT-X-TARGETDURATION:8
#EXTINF:8,
video.ts
#EXTINF:8,
ad.ts
"""
            )

        async def segment(request):
            return web.Response(body=b"ts")

        source_app = web.Application()
        source_app.router.add_get("/index.m3u8", playlist)
        source_app.router.add_get("/{name}.ts", segment)
        source_runner = web.AppRunner(source_app)
        await source_runner.setup()
        source_site = web.TCPSite(source_runner, "127.0.0.1", 0)
        await source_site.start()
        source_port = source_site._server.sockets[0].getsockname()[1]

        proxy = ProxyServer(port=0, filter_keywords=["ad.ts"])
        await proxy.start()
        proxy_port = proxy._site._server.sockets[0].getsockname()[1]
        proxy.port = proxy_port

        import aiohttp

        try:
            src = f"http://127.0.0.1:{source_port}/index.m3u8"
            async with aiohttp.ClientSession() as session:
                async with session.get(proxy.get_stream_url(src)) as response:
                    text = await response.text()
                assert "/ts?src=" in text
                assert "video.ts" in text
                assert "ad.ts" not in text
        finally:
            await proxy.stop()
            await source_runner.cleanup()

    asyncio.run(run())
