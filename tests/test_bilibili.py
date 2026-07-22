from m3u8_downloader.core.bilibili import (
    BilibiliRequestConfig,
    BilibiliRequestError,
    BilibiliRequestSession,
    BilibiliProvider,
    BilibiliMediaManifest,
    BilibiliPage,
    BilibiliSelectionPolicy,
    BilibiliTrack,
    build_bilibili_headers,
    is_bilibili_url,
    is_bilibili_page_url,
    parse_bilibili_input,
    prepare_bilibili_request,
    _parse_tracks,
)
from m3u8_downloader.core.bilibili_auth import _cookie_from_login_url
from m3u8_downloader.core.bilibili_stream import resolve_bilibili_playback


class _JsonResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def close(self):
        return None


class _StatusResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}

    def close(self):
        return None


class _JsonHttp:
    def __init__(self, payload):
        self.payload = payload

    def request(self, *args, **kwargs):
        return _JsonResponse(self.payload)


class _StatusHttp:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.calls = 0

    def request(self, *args, **kwargs):
        self.calls += 1
        return _StatusResponse(self.status_code, self.headers)


class _SequenceHttp:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.urls = []

    def request(self, method, url, **kwargs):
        self.urls.append(url)
        return _JsonResponse(self.payloads.pop(0))


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


def test_bilibili_request_keeps_https_for_cmcc_cdn():
    url = "https://upos-sz-mirrorali-cmcc.bilivideo.com/video.m4s?token=secret"

    request_url, _headers = prepare_bilibili_request(url)

    assert request_url == url


def test_bilibili_track_prefers_backup_without_explicit_port():
    tracks = _parse_tracks(
        [{
            "baseUrl": "https://upos-sz-mirrorali.bilivideo.com:443/video.m4s",
            "backupUrl": ["https://upos-sz-mirrorali.bilivideo.com/video.m4s"],
            "id": 80,
            "codecid": 7,
        }],
        "video",
    )

    assert tracks[0].url == "https://upos-sz-mirrorali.bilivideo.com/video.m4s"
    assert tracks[0].backup_urls == ("https://upos-sz-mirrorcoso1.bilivideo.com/video.m4s",)


def test_manual_bilibili_mode_adds_headers_without_rewriting_unrelated_urls():
    url = "https://cdn.example/video.bin?token=secret"

    request_url, headers = prepare_bilibili_request(url, enabled=True)

    assert request_url == url
    assert headers == {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com"}


def test_bilibili_input_normalizes_short_and_page_url_kinds():
    assert parse_bilibili_input("https://b23.tv/abc").kind == "short"
    assert is_bilibili_page_url("https://b23.tv/abc")
    video = parse_bilibili_input("https://www.bilibili.com/video/BV1mz4y1M7a6?t=8.4")
    assert video.kind == "video"
    assert video.bvid == "BV1mz4y1M7a6"


def test_bilibili_cdn_is_not_treated_as_a_page_url():
    assert not is_bilibili_page_url("https://xy123.bilivideo.com/video.m4s?token=secret")


def test_api_bad_request_is_not_reported_as_authentication_failure():
    session = BilibiliRequestSession(
        BilibiliRequestConfig(),
        http=_JsonHttp({"code": -400, "message": "请求错误"}),
    )

    try:
        session.request_json("https://api.bilibili.com/x/player/wbi/playurl")
    except BilibiliRequestError as exc:
        assert exc.category == "api"
        assert exc.api_code == -400
    else:
        raise AssertionError("expected BilibiliRequestError")


def test_http_rate_limit_is_not_retried():
    http = _StatusHttp(429)
    session = BilibiliRequestSession(
        BilibiliRequestConfig(retries=3, request_interval=0),
        http=http,
    )

    try:
        session.request_json("https://api.bilibili.com/x/player/wbi/playurl")
    except BilibiliRequestError as exc:
        assert exc.category == "rate_limit"
        assert exc.status_code == 429
    else:
        raise AssertionError("expected BilibiliRequestError")

    assert http.calls == 1


def test_anonymous_play_request_uses_bbdown_try_look_parameter():
    http = _SequenceHttp([
        {
            "code": 0,
            "data": {
                "aid": 1,
                "bvid": "BV1",
                "title": "title",
                "pages": [{"page": 1, "cid": 2, "part": "P1", "duration": 1}],
            },
        },
        {
            "code": -101,
            "data": {
                "wbi_img": {
                    "img_url": "https://i0.hdslb.com/bfs/wbi/" + "a" * 64 + ".png",
                    "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "b" * 64 + ".png",
                },
            },
        },
        {
            "code": 0,
            "data": {
                "timelength": 1000,
                "dash": {
                    "video": [{"baseUrl": "https://video.example/video.m4s", "id": 32, "codecid": 7}],
                    "audio": [],
                },
            },
        },
    ])
    provider = BilibiliProvider(BilibiliRequestSession(BilibiliRequestConfig(), http=http))

    provider.resolve("https://www.bilibili.com/video/BV1")

    assert "try_look=1" in http.urls[-1]


def test_bilibili_playback_resolution_returns_dash_backup_tracks():
    http = _SequenceHttp([
        {
            "code": 0,
            "data": {
                "aid": 1,
                "bvid": "BV1",
                "title": "title",
                "pages": [{"page": 1, "cid": 2, "part": "P1", "duration": 1}],
            },
        },
        {
            "code": -101,
            "data": {
                "wbi_img": {
                    "img_url": "https://i0.hdslb.com/bfs/wbi/" + "a" * 64 + ".png",
                    "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "b" * 64 + ".png",
                },
            },
        },
        {
            "code": 0,
            "data": {
                "timelength": 1000,
                "dash": {
                    "video": [{
                        "baseUrl": "https://video.example/video.m4s",
                        "backupUrl": ["https://backup.example/video.m4s"],
                        "id": 80,
                        "codecid": 7,
                    }],
                    "audio": [],
                },
            },
        },
    ])
    playback = resolve_bilibili_playback(
        "https://www.bilibili.com/video/BV1",
        headers={"Cookie": "SESSDATA=test"},
        http=http,
    )

    assert playback.video.url == "https://video.example/video.m4s"
    assert playback.video.backup_urls == ("https://backup.example/video.m4s",)
    assert playback.audio is None


def test_config_cookie_is_added_to_bilibili_headers_without_overwriting_explicit_cookie():
    headers = build_bilibili_headers({"bilibili_cookie": "SESSDATA=config"}, url="https://www.bilibili.com/video/BV1")
    assert headers["Cookie"] == "SESSDATA=config"
    explicit = build_bilibili_headers({"bilibili_cookie": "SESSDATA=config"}, {"Cookie": "SESSDATA=explicit"})
    assert explicit["Cookie"] == "SESSDATA=explicit"


def test_anonymous_nav_response_can_supply_wbi_data():
    session = BilibiliRequestSession(
        BilibiliRequestConfig(),
        http=_JsonHttp({
            "code": -101,
            "message": "账号未登录",
            "data": {
                "wbi_img": {
                    "img_url": "https://i0.hdslb.com/bfs/wbi/" + "a" * 64 + ".png",
                    "sub_url": "https://i0.hdslb.com/bfs/wbi/" + "b" * 64 + ".png",
                },
            },
        }),
    )

    payload = session.request_json(
        "https://api.bilibili.com/x/web-interface/nav",
        allow_codes=frozenset({-101}),
    )

    assert payload["code"] == -101
    assert not session.has_cookie
    assert len(session._load_wbi_key()) == 32


def test_qr_login_cookie_parser_keeps_only_login_cookies():
    cookie = _cookie_from_login_url(
        "https://passport.bilibili.com/cross?SESSDATA=session%2Bvalue&bili_jct=csrf&gourl=https%3A%2F%2Fwww.bilibili.com"
    )

    assert cookie == "SESSDATA=session%2Bvalue; bili_jct=csrf"


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
