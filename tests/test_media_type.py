from m3u8_downloader.core.media_type import (
    MediaKind,
    detect_media_type_from_body,
    detect_media_type_from_content_type,
    detect_media_type_from_url,
)


def test_detect_media_type_from_url():
    assert detect_media_type_from_url("https://cdn.test/master.m3u8").kind == MediaKind.HLS
    assert detect_media_type_from_url("https://cdn.test/manifest.mpd").kind == MediaKind.DASH
    assert detect_media_type_from_url("rtsp://camera.test/live").kind == MediaKind.RTSP
    assert detect_media_type_from_url("https://cdn.test/video.mp4?token=1").kind == MediaKind.PROGRESSIVE


def test_detect_media_type_from_content_type():
    assert detect_media_type_from_content_type("application/vnd.apple.mpegurl; charset=utf-8").kind == MediaKind.HLS
    assert detect_media_type_from_content_type("application/dash+xml").kind == MediaKind.DASH
    assert detect_media_type_from_content_type("video/webm").kind == MediaKind.PROGRESSIVE


def test_detect_media_type_from_body():
    assert detect_media_type_from_body("#EXTM3U\n#EXT-X-VERSION:3").kind == MediaKind.HLS
    assert detect_media_type_from_body("<?xml version='1.0'?><MPD></MPD>").kind == MediaKind.DASH
    assert detect_media_type_from_body("<SmoothStreamingMedia></SmoothStreamingMedia>").kind == MediaKind.SMOOTH
