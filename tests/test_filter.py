from m3u8_downloader.core.filter import filter_playlist, is_ad_segment
from m3u8_downloader.core.parser import Playlist, Segment


def test_is_ad_segment_keyword():
    segment = Segment(duration=5, url="https://cdn.test/ads/banner.ts", title="")
    assert is_ad_segment(segment, ["banner"]) is True


def test_filter_playlist_keeps_non_ads():
    playlist = Playlist(
        segments=[
            Segment(duration=5, url="https://cdn.test/video-1.ts"),
            Segment(duration=5, url="https://cdn.test/ad-1.ts"),
            Segment(duration=5, url="https://cdn.test/video-2.ts"),
        ]
    )

    filtered = filter_playlist(playlist, ["/ad-"])

    assert [segment.url for segment in filtered.segments] == [
        "https://cdn.test/video-1.ts",
        "https://cdn.test/video-2.ts",
    ]


def test_filter_playlist_regex():
    segment = Segment(duration=5, url="https://cdn.test/promo_001.ts")
    assert is_ad_segment(segment, [r"promo_\d+"], use_regex=True) is True
