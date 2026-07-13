from m3u8_downloader.core.direct_downloader import download_direct_media


class FakeResponse:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def iter_content(self, chunk_size):
        yield b"media"


def test_download_direct_media_streams_to_part_file(tmp_path, monkeypatch):
    output = tmp_path / "audio.m4a"
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append((url, headers, stream, allow_redirects, timeout))
        return FakeResponse()

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    assert download_direct_media("https://cdn.test/audio.m4a", output, {"Referer": "https://example.com"}) is True

    assert output.read_bytes() == b"media"
    assert not output.with_name("audio.m4a.part").exists()
    assert calls == [("https://cdn.test/audio.m4a", {"Referer": "https://example.com"}, True, True, 30)]
