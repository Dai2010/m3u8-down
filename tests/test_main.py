from m3u8_downloader.main import _load_media_playlist


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
