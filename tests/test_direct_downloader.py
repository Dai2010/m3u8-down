from m3u8_downloader.core.direct_downloader import DirectDownloadError, download_direct_media


class FakeResponse:
    def __init__(self, status_code=200, chunks=(b"media",), headers=None):
        self.status_code = status_code
        self.chunks = chunks
        self.headers = headers or {}

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
        return FakeResponse(
            status_code=206,
            chunks=(b"suffix",),
            headers={"Content-Length": "6", "Content-Range": "bytes 6-11/12"},
        )

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    assert download_direct_media("https://cdn.example/video.m4s", output, retries=1) is True

    assert output.read_bytes() == b"prefixsuffix"
    assert calls == [{"Range": "bytes=6-"}]


def test_download_direct_media_restarts_after_invalid_range(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    output.with_name("video.m4s.part").write_bytes(b"stale")
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(headers.copy())
        return FakeResponse(status_code=206, chunks=(b"wrong",), headers={"Content-Length": "5", "Content-Range": "bytes 0-4/10"})

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    try:
        download_direct_media("https://cdn.example/video.m4s", output, retries=1)
    except DirectDownloadError as exc:
        assert exc.category == "download_body"
    else:
        raise AssertionError("expected DirectDownloadError")

    assert output.with_name("video.m4s.part").read_bytes() == b"stale"
    assert calls == [{"Range": "bytes=5-"}]


def test_download_direct_media_clears_part_after_range_not_satisfiable(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    output.with_name("video.m4s.part").write_bytes(b"stale")
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(headers.copy())
        if len(calls) == 1:
            return FakeResponse(status_code=416)
        return FakeResponse(status_code=200, chunks=(b"complete",), headers={"Content-Length": "8"})

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    assert download_direct_media("https://cdn.example/video.m4s", output, retries=1) is True

    assert output.read_bytes() == b"complete"
    assert calls == [{"Range": "bytes=5-"}, {}]


def test_download_direct_media_rejects_html_response(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"

    def fake_get(url, headers, stream, allow_redirects, timeout):
        return FakeResponse(status_code=200, chunks=(b"<html>denied</html>",), headers={"Content-Type": "text/html"})

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    try:
        download_direct_media("https://cdn.example/video.m4s", output, retries=1)
    except DirectDownloadError as exc:
        assert exc.category == "download_body"
        assert exc.content_type == "text/html"
    else:
        raise AssertionError("expected DirectDownloadError")


def test_download_direct_media_preserves_signed_bilibili_media_url(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    calls = []

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(url)
        return FakeResponse(status_code=200, chunks=(b"media",), headers={"Content-Length": "5"})

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    signed_url = "https://primary.bilivideo.com/video.m4s?token=secret"
    assert download_direct_media(
        signed_url,
        output,
        bilibili_compat=True,
        preserve_bilibili_media_url=True,
        retries=1,
    ) is True

    assert calls == [signed_url]


def test_download_direct_media_tries_bilibili_cdn_variants_after_403(tmp_path, monkeypatch):
    output = tmp_path / "video.m4s"
    calls = []
    signed_url = "https://upos-sz-mirrorhwb.bilivideo.com/video.m4s?token=secret"

    def fake_get(url, headers, stream, allow_redirects, timeout):
        calls.append(url)
        if url == signed_url:
            return FakeResponse(status_code=403, headers={"Content-Type": "text/html"})
        return FakeResponse(status_code=200, chunks=(b"media",), headers={"Content-Length": "5"})

    monkeypatch.setattr("m3u8_downloader.core.direct_downloader.requests.get", fake_get)

    assert download_direct_media(
        signed_url,
        output,
        bilibili_compat=True,
        preserve_bilibili_media_url=True,
        retries=1,
    ) is True

    assert calls == [
        signed_url,
        "http://upos-sz-mirrorhwb.bilivideo.com/video.m4s?token=secret",
    ]


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
