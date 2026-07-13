from m3u8_downloader.core.ffmpeg_downloader import download_with_ffmpeg


def test_download_with_ffmpeg_passes_headers(tmp_path, monkeypatch):
    output = tmp_path / "video.mp4"
    command_holder = {}

    def fake_run(command, capture_output, text, check):
        command_holder["command"] = command

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr("m3u8_downloader.core.ffmpeg_downloader.subprocess.run", fake_run)

    assert download_with_ffmpeg("https://cdn.test/video.mp4", output, {"Referer": "https://example.com"}) is True

    command = command_holder["command"]
    assert command[:2] == ["ffmpeg", "-y"]
    assert "-headers" in command
    assert "Referer: https://example.com\r\n" in command
    assert command[-3:] == ["-c", "copy", str(output)]
