from m3u8_downloader.core.bilibili import (
    BilibiliMediaManifest,
    BilibiliPage,
    BilibiliSelectionPolicy,
    BilibiliTrack,
    build_bilibili_headers,
    is_bilibili_url,
    parse_bilibili_input,
    prepare_bilibili_request,
)


def test_bilibili_domain_detection_accepts_first_party_and_cdn_hosts():
    assert is_bilibili_url("https://www.bilibili.com/video/BV1")
    assert is_bilibili_url("https://xy123.hd.bilivideo.com/video.m4s")
    assert is_bilibili_url("https://cdn.example.bilivideo.cn/video.m4s")
    assert not is_bilibili_url("https://bilivideo.example/video.m4s")


def test_bilibili_request_adds_headers_and_converts_cdn_to_http():
    url, headers = prepare_bilibili_request("https://xy123.bilivideo.com/video.m4s?token=secret")

    assert url == "http://xy123.bilivideo.com/video.m4s?token=secret"
    assert headers == {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"}


def test_bilibili_request_preserves_android_platform_and_mcdn_port():
    android_url = "https://xy123.bilivideo.com/video.m4s?platform=android_tv_yst"
    mcdn_url = "https://xy123.mcdn.bilivideo.cn:443/video.m4s?token=secret"

    android_request, android_headers = prepare_bilibili_request(android_url)
    mcdn_request, mcdn_headers = prepare_bilibili_request(mcdn_url)

    assert android_request == android_url.replace("https://", "http://")
    assert android_headers == {"User-Agent": "Mozilla/5.0"}
    assert mcdn_request == mcdn_url
    assert mcdn_headers == {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"}


def test_manual_bilibili_mode_adds_headers_without_rewriting_unrelated_urls():
    url = "https://cdn.example/video.bin?token=secret"

    request_url, headers = prepare_bilibili_request(url, enabled=True)

    assert request_url == url
    assert headers == {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"}


def test_bilibili_input_normalizes_short_and_page_url_kinds():
    assert parse_bilibili_input("https://b23.tv/abc").kind == "short"
    video = parse_bilibili_input("https://www.bilibili.com/video/BV1xx411c7mD?p=2")
    assert video.kind == "video"
    assert video.bvid == "BV1xx411c7mD"


def test_config_cookie_is_added_to_bilibili_headers_without_overwriting_explicit_cookie():
    headers = build_bilibili_headers({"bilibili_cookie": "SESSDATA=config"}, url="https://www.bilibili.com/video/BV1")
    assert headers["Cookie"] == "SESSDATA=config"
    explicit = build_bilibili_headers({"bilibili_cookie": "SESSDATA=config"}, {"Cookie": "SESSDATA=explicit"})
    assert explicit["Cookie"] == "SESSDATA=explicit"


def test_manifest_selection_uses_codec_policy_before_bandwidth():
    avc = BilibiliTrack("https://video/avc", (), "video", quality_id=80, bandwidth=100, codec_id=7)
    hevc = BilibiliTrack("https://video/hevc", (), "video", quality_id=80, bandwidth=200, codec_id=12)
    selected_page = BilibiliPage(1, "1", "", 0)
    manifest = BilibiliMediaManifest(
        source_url="https://www.bilibili.com/video/BV1",
        input=parse_bilibili_input("https://www.bilibili.com/video/BV1"),
        title="title",
        description="",
        cover_url="",
        pages=(selected_page,),
        selected_page=selected_page,
        video_tracks=(avc, hevc),
        audio_tracks=(),
        subtitles=(),
    )
    assert manifest.select_video(BilibiliSelectionPolicy()).url == "https://video/avc"
