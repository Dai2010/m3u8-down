from m3u8_downloader.core.bilibili import is_bilibili_url, prepare_bilibili_request


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
