from m3u8_downloader.core.downloader import Downloader
from m3u8_downloader.core.parser import Segment


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield b"one"
        yield b"two"


def test_downloader_writes_segments_in_order(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, headers, stream, timeout):
        calls.append((url, headers, stream, timeout))
        return FakeResponse()

    monkeypatch.setattr("m3u8_downloader.core.downloader.requests.get", fake_get)

    paths = Downloader(threads=2, headers={"Referer": "x"}).download(
        [Segment(1, "https://cdn.test/2.ts"), Segment(1, "https://cdn.test/1.ts")],
        tmp_path,
    )

    assert [path.name for path in paths] == ["00000.ts", "00001.ts"]
    assert paths[0].read_bytes() == b"onetwo"
    assert calls[0][1] == {"Referer": "x"}


def test_downloader_skips_existing_segment(tmp_path, monkeypatch):
    existing = tmp_path / "00000.ts"
    existing.write_bytes(b"done")

    def fake_get(*args, **kwargs):
        raise AssertionError("should not download existing files")

    monkeypatch.setattr("m3u8_downloader.core.downloader.requests.get", fake_get)

    paths = Downloader().download([Segment(1, "https://cdn.test/existing.ts")], tmp_path)

    assert paths == [existing]
