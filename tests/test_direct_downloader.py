from m3u8_downloader.core.direct_downloader import DirectDownloadError, download_direct_media


class FakeResponse:
    def __init__(self, status_code=200, chunks=(b"media",)):
        self.status_code = status_code
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def iter_content(self, chunk_size):
        yield from self.chunks


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


def test_download_direct_media_resumes_existing_part_file(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    part = output.with_name("video.m4s.part")
    part.write_bytes(b"prefix")
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(headers)
        return FakeResponse(status_code=206, chunks=(b"suffix",))

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    assert download_direct_media("https://cdn.example/video.m4s", output, retries=1) is True

    assert output.read_bytes() == b"prefixsuffix"
    assert calls == [{"Range": "bytes=6-"}]


def test_download_direct_media_stops_after_bilibili_rate_limit(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(url)
        return FakeResponse(status_code=429)

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    try:
        download_direct_media(
            "https://video.bilivideo.com/video.m4s",
            output,
            retries=3,
            backup_urls=("https://backup.bilivideo.com/video.m4s",),
        )
    except DirectDownloadError as exc:
        assert exc.status_code == 429
    else:
        raise AssertionError("expected DirectDownloadError")

    assert calls == ["http://video.bilivideo.com/video.m4s"]


def test_download_direct_media_uses_backup_after_expired_primary(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(url)
        if "primary" in url:
            return FakeResponse(status_code=403)
        return FakeResponse(status_code=200, chunks=(b"backup",))

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    assert download_direct_media(
        "https://primary.bilivideo.com/video.m4s",
        output,
        retries=1,
        backup_urls=("https://backup.bilivideo.com/video.m4s",),
    ) is True

    assert output.read_bytes() == b"backup"
    assert calls == [
        "http://primary.bilivideo.com/video.m4s",
        "http://backup.bilivideo.com/video.m4s",
    ]
