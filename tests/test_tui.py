from m3u8_downloader.tui.app import M3U8DownloaderTUI


def test_tui_app_can_be_constructed():
    app = M3U8DownloaderTUI()
    assert app.config["threads"]
