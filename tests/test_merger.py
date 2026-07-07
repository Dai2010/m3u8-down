from m3u8_downloader.core.merger import merge_to_mp4


class Result:
    returncode = 0
    stderr = ""


def test_merge_to_mp4_invokes_ffmpeg_concat_list(tmp_path, monkeypatch):
    ts_file = tmp_path / "00000.ts"
    ts_file.write_bytes(b"ts")
    output = tmp_path / "out.mp4"
    command_holder = {}

    def fake_run(command, capture_output, text, check):
        command_holder["command"] = command
        return Result()

    monkeypatch.setattr("m3u8_downloader.core.merger.subprocess.run", fake_run)

    assert merge_to_mp4([ts_file], output, ffmpeg_path="ffmpeg-test") is True
    assert command_holder["command"][:6] == ["ffmpeg-test", "-y", "-f", "concat", "-safe", "0"]
