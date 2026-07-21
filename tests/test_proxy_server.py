import asyncio
from urllib.parse import parse_qs, urlsplit

from aiohttp import web

from m3u8_downloader.core.bilibili import BilibiliTrack
from m3u8_downloader.core.proxy_server import ProxyServer


def test_proxy_stream_filters_ad_segments():
    async def run():
        async def playlist(request):
            return web.Response(
                text="""#EXTM3U
#EXT-X-VERSION:7
#EXT-X-TARGETDURATION:8
#EXT-X-MAP:URI="init.mp4"
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
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
                assert "#EXT-X-MAP:" in text
                assert "init.mp4" in text
                assert "#EXT-X-KEY:" in text
                assert "key.bin" in text
        finally:
            await proxy.stop()
            await source_runner.cleanup()

    asyncio.run(run())


def test_proxy_serves_resolved_bilibili_tracks_as_dash():
    async def run():
        proxy = ProxyServer(port=0)
        await proxy.start()
        try:
            video = BilibiliTrack(
                "https://primary.bilivideo.com/video.m4s",
                ("https://backup.bilivideo.com/video.m4s",),
                "video",
                quality_id=80,
                bandwidth=1000,
                codec_id=7,
                width=1920,
                height=1080,
            )
            audio = BilibiliTrack(
                "https://audio.bilivideo.com/audio.m4s",
                (),
                "audio",
                bandwidth=128,
            )
            url = proxy.get_bilibili_dash_url(video, audio, duration_ms=1234)

            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    text = await response.text()
            assert response.content_type == "application/dash+xml"
            assert "mediaPresentationDuration=\"PT1.234S\"" in text
            assert "/media?dash=" in text
            assert "primary.bilivideo.com" not in text
            assert "audio" in text
        finally:
            await proxy.stop()

    asyncio.run(run())


def test_proxy_switches_to_backup_track_after_primary_response_failure():
    async def run():
        async def primary(request):
            return web.Response(status=403)

        async def backup(request):
            return web.Response(body=b"backup-media", content_type="video/mp4")

        source_app = web.Application()
        source_app.router.add_get("/primary.m4s", primary)
        source_app.router.add_get("/backup.m4s", backup)
        source_runner = web.AppRunner(source_app)
        await source_runner.setup()
        source_site = web.TCPSite(source_runner, "127.0.0.1", 0)
        await source_site.start()
        source_port = source_site._server.sockets[0].getsockname()[1]

        proxy = ProxyServer(port=0)
        await proxy.start()
        try:
            video = BilibiliTrack(
                f"http://127.0.0.1:{source_port}/primary.m4s",
                (f"http://127.0.0.1:{source_port}/backup.m4s",),
                "video",
            )
            mpd_url = proxy.get_bilibili_dash_url(video)
            source_id = parse_qs(urlsplit(mpd_url).query)["id"][0]

            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{proxy.host}:{proxy.port}/media?dash={source_id}&track=video") as response:
                    body = await response.read()
            assert response.status == 200
            assert body == b"backup-media"
        finally:
            await proxy.stop()
            await source_runner.cleanup()

    asyncio.run(run())
