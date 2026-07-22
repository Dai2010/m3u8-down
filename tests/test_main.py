import sys

import m3u8_downloader.main as main_module
from m3u8_downloader.core.media_type import MediaInfo, MediaKind
from m3u8_downloader.core.bilibili import BilibiliPage
from m3u8_downloader.main import _load_media_playlist, _parse_bilibili_page_spec


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_load_media_playlist_selects_best_master_variant(monkeypatch):
    responses = {
        "https://cdn.test/master.m3u8": """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=1
low.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2
high.m3u8
""",
        "https://cdn.test/high.m3u8": """#EXTM3U
#EXT-X-TARGETDURATION:8
#EXTINF:8,
seg.ts
""",
    }

    def fake_get(url, headers, timeout):
        return FakeResponse(responses[url])

    monkeypatch.setattr("m3u8_downloader.main.requests.get", fake_get)

    playlist = _load_media_playlist("https://cdn.test/master.m3u8", {}, -1)

    assert playlist.segments[0].url == "https://cdn.test/seg.ts"


def test_main_without_url_launches_tui(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["m3u8-downloader"])
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "_launch_tui", lambda: calls.append("tui"))

    main_module.main()

    assert calls == ["tui"]


def test_main_downloads_progressive_media_directly(monkeypatch, tmp_path, capsys):
    calls = []
    output = tmp_path / "video.mp4"

    monkeypatch.setattr(sys, "argv", ["m3u8-downloader", "https://cdn.test/video.mp4", "-o", str(output)])
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "load_config", lambda: {"headers": {}, "filter_keywords": [], "threads": 16})
    monkeypatch.setattr(main_module, "detect_media_type", lambda url, headers, **kwargs: MediaInfo(MediaKind.PROGRESSIVE, "url"))
    monkeypatch.setattr(main_module, "require_ffmpeg", lambda: (_ for _ in ()).throw(AssertionError("should not require ffmpeg")))
    monkeypatch.setattr(
        main_module,
        "download_direct_media",
        lambda url, target, headers, **kwargs: calls.append((url, target, headers, kwargs)),
    )
    monkeypatch.setattr(main_module, "download_with_ffmpeg", lambda *args: (_ for _ in ()).throw(AssertionError("should not use ffmpeg")))
    monkeypatch.setattr(main_module, "_load_media_playlist", lambda *args: (_ for _ in ()).throw(AssertionError("should not load hls playlist")))

    main_module.main()

    assert calls == [("https://cdn.test/video.mp4", output, {}, {"bilibili_compat": False})]
    assert "detected direct media" in capsys.readouterr().out


def test_main_downloads_stream_manifests_with_ffmpeg(monkeypatch, tmp_path, capsys):
    calls = []
    output = tmp_path / "video.mp4"

    monkeypatch.setattr(sys, "argv", ["m3u8-downloader", "https://cdn.test/manifest.mpd", "-o", str(output)])
    monkeypatch.setattr(main_module, "setup_logging", lambda: None)
    monkeypatch.setattr(main_module, "load_config", lambda: {"headers": {}, "filter_keywords": [], "threads": 16})
    monkeypatch.setattr(main_module, "detect_media_type", lambda url, headers, **kwargs: MediaInfo(MediaKind.DASH, "url"))
    monkeypatch.setattr(main_module, "require_ffmpeg", lambda: None)
    monkeypatch.setattr(main_module, "download_direct_media", lambda *args: (_ for _ in ()).throw(AssertionError("should not use direct download")))
    monkeypatch.setattr(
        main_module,
        "download_with_ffmpeg",
        lambda url, target, headers, **kwargs: calls.append((url, target, headers, kwargs)),
    )
    monkeypatch.setattr(main_module, "_load_media_playlist", lambda *args: (_ for _ in ()).throw(AssertionError("should not load hls playlist")))

    main_module.main()

    assert calls == [("https://cdn.test/manifest.mpd", output, {}, {"bilibili_compat": False})]
    assert "detected MPEG-DASH/mpd" in capsys.readouterr().out


def test_default_output_uses_direct_media_extension():
    assert main_module._default_output_for_url("https://cdn.test/movie.webm?token=1") == "video.webm"
    assert main_module._default_output_for_url("https://cdn.test/master.m3u8") == "video.mp4"


def test_bilibili_page_spec_supports_single_multiple_range_and_all():
    pages = tuple(BilibiliPage(index, str(index), f"P{index}", 0) for index in range(1, 5))

    assert _parse_bilibili_page_spec("2", pages) == [2]
    assert _parse_bilibili_page_spec("1,3,3", pages) == [1, 3]
    assert _parse_bilibili_page_spec("2-4", pages) == [2, 3, 4]
    assert _parse_bilibili_page_spec("ALL", pages) == [1, 2, 3, 4]
