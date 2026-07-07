from m3u8_downloader.core.parser import Key, Segment, parse_playlist, playlist_to_m3u8, resolve_url


def test_parse_media_playlist_resolves_segments_and_metadata():
    playlist = parse_playlist(
        """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:42
#EXT-X-PLAYLIST-TYPE:VOD
#EXTINF:8.5,First
seg-1.ts
#EXT-X-DISCONTINUITY
#EXTINF:9.0,Second
/video/seg-2.ts
""",
        "https://example.com/path/index.m3u8",
    )

    assert playlist.version == 3
    assert playlist.target_duration == 10
    assert playlist.media_sequence == 42
    assert playlist.playlist_type == "VOD"
    assert playlist.segments[0].url == "https://example.com/path/seg-1.ts"
    assert playlist.segments[1].url == "https://example.com/video/seg-2.ts"
    assert playlist.segments[1].discontinuity is True


def test_parse_master_playlist():
    playlist = parse_playlist(
        """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,CODECS="avc1.42e01e,mp4a.40.2"
low/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1600000,RESOLUTION=1280x720
high/index.m3u8
""",
        "https://cdn.test/master.m3u8",
    )

    assert playlist.is_master is True
    assert len(playlist.variants) == 2
    assert playlist.variants[0].codecs == "avc1.42e01e,mp4a.40.2"
    assert playlist.variants[1].url == "https://cdn.test/high/index.m3u8"
    assert playlist.best_variant().url == "https://cdn.test/high/index.m3u8"


def test_resolve_url():
    assert resolve_url("https://a.test/dir/index.m3u8", "one.ts") == "https://a.test/dir/one.ts"


def test_playlist_to_m3u8_serializes_filtered_media_playlist():
    playlist = parse_playlist(
        """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:8
#EXT-X-KEY:METHOD=AES-128,URI="key.bin",IV=0x1
#EXTINF:8.0,Video
seg.ts
""",
        "https://cdn.test/path/index.m3u8",
    )

    content = playlist_to_m3u8(playlist)

    assert "#EXT-X-KEY:METHOD=AES-128,URI=\"https://cdn.test/path/key.bin\",IV=0x1" in content
    assert "#EXTINF:8,Video" in content
    assert "https://cdn.test/path/seg.ts" in content
    assert content.endswith("#EXT-X-ENDLIST\n")


def test_playlist_to_m3u8_emits_key_changes():
    content = playlist_to_m3u8(
        parse_playlist(
            """#EXTM3U
#EXT-X-TARGETDURATION:8
#EXT-X-KEY:METHOD=AES-128,URI="a.key"
#EXTINF:8,
a.ts
#EXT-X-KEY:METHOD=AES-128,URI="b.key"
#EXTINF:8,
b.ts
""",
            "https://cdn.test/index.m3u8",
        )
    )

    assert content.count("#EXT-X-KEY") == 2
