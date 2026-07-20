from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import md5
import re
from time import sleep, time
from typing import Any, Mapping
from urllib.parse import quote, urlsplit, urlunsplit

import requests


BILIBILI_HOST_SUFFIXES = (
    "bilibili.com",
    "bilibili.tv",
    "bilivideo.com",
    "bilivideo.cn",
    "b23.tv",
    "bili2233.cn",
)
DEFAULT_BILIBILI_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
DEFAULT_BILIBILI_REFERER = "https://www.bilibili.com"
DEFAULT_BILIBILI_API_HOST = "api.bilibili.com"
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
WBI_MIXIN_KEY_TABLE = (
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 19, 29, 7, 39, 13, 42, 20, 37, 34, 14,
    4, 17, 48, 22, 30, 11, 24, 28, 55, 54, 51, 56, 1, 21, 44, 12,
    25, 16, 36, 38, 40, 6, 52, 62, 26, 0, 41, 57, 63, 60, 61, 59,
)


@dataclass(frozen=True)
class BilibiliRequestConfig:
    headers: Mapping[str, str] = field(default_factory=dict)
    cookie: str = ""
    user_agent: str = DEFAULT_BILIBILI_USER_AGENT
    referer: str = DEFAULT_BILIBILI_REFERER
    origin: str = DEFAULT_BILIBILI_REFERER
    timeout: float = 30.0
    retries: int = 3
    api_host: str = DEFAULT_BILIBILI_API_HOST

    def headers_for(self, url: str, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        merged = {key: value for key, value in self.headers.items() if value}
        if extra:
            merged.update({key: value for key, value in extra.items() if value})
        if self.user_agent and not _has_header(merged, "User-Agent"):
            merged["User-Agent"] = self.user_agent
        if self.referer and not _has_header(merged, "Referer") and not _uses_android_platform(url):
            merged["Referer"] = self.referer
        if self.origin and not _has_header(merged, "Origin") and is_bilibili_url(url):
            merged["Origin"] = self.origin
        if self.cookie and not _has_header(merged, "Cookie"):
            merged["Cookie"] = self.cookie
        return merged


def build_bilibili_headers(
    config: Mapping[str, Any] | None = None,
    extra: Mapping[str, str] | None = None,
    url: str = "",
) -> dict[str, str]:
    source = config or {}
    headers = {key: value for key, value in (source.get("headers", {}) or {}).items() if value}
    headers.update({key: value for key, value in (extra or {}).items() if value})
    cookie = str(source.get("bilibili_cookie", "") or "")
    if cookie and url and is_bilibili_url(url) and not _has_header(headers, "Cookie"):
        headers["Cookie"] = cookie
    if url and is_bilibili_url(url) and not _has_header(headers, "Origin"):
        headers["Origin"] = DEFAULT_BILIBILI_REFERER
    return headers


def is_bilibili_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in BILIBILI_HOST_SUFFIXES)


def prepare_bilibili_request(
    url: str,
    headers: dict[str, str] | None = None,
    enabled: bool = False,
    cookie: str = "",
) -> tuple[str, dict[str, str]]:
    request_headers = {key: value for key, value in (headers or {}).items() if value}
    if not enabled and not is_bilibili_url(url):
        return url, request_headers

    if not _has_header(request_headers, "User-Agent"):
        request_headers["User-Agent"] = "Mozilla/5.0"
    if not _uses_android_platform(url) and not _has_header(request_headers, "Referer"):
        request_headers["Referer"] = DEFAULT_BILIBILI_REFERER
    if cookie and not _has_header(request_headers, "Cookie"):
        request_headers["Cookie"] = cookie

    parsed = urlsplit(url)
    if parsed.scheme.lower() == "https" and _is_bilivideo_host(parsed.hostname) and not _keep_https_for_host(parsed):
        return urlunsplit(("http", parsed.netloc, parsed.path, parsed.query, parsed.fragment)), request_headers
    return url, request_headers


class BilibiliRequestError(RuntimeError):
    def __init__(self, category: str, message: str, url: str = "", status_code: int | None = None):
        self.category = category
        self.status_code = status_code
        self.url = url
        super().__init__(message)


class BilibiliProviderError(RuntimeError):
    pass


class BilibiliRequestSession:
    def __init__(self, config: BilibiliRequestConfig | None = None, http: requests.Session | None = None):
        self.config = config or BilibiliRequestConfig()
        self.http = http or requests.Session()
        self._wbi_key = ""
        self._wbi_key_expires_at = 0.0

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        request_url, request_headers = prepare_bilibili_request(
            url,
            self.config.headers_for(url, headers),
            enabled=True,
            cookie=self.config.cookie,
        )
        options = {"allow_redirects": True, "timeout": self.config.timeout}
        options.update(kwargs)
        attempts = max(1, self.config.retries + 1)

        for attempt in range(attempts):
            try:
                response = self.http.request(method, request_url, headers=request_headers, **options)
            except requests.RequestException as exc:
                if attempt + 1 >= attempts:
                    raise BilibiliRequestError("network", "B 站网络请求失败", request_url) from exc
                sleep(_retry_delay(attempt))
                continue

            if response.status_code in TRANSIENT_HTTP_STATUS and attempt + 1 < attempts:
                response.close()
                sleep(_retry_delay(attempt))
                continue
            if response.status_code >= 400:
                category = _http_error_category(response.status_code)
                response.close()
                raise BilibiliRequestError(category, f"B 站请求失败：HTTP {response.status_code}", request_url, response.status_code)
            return response

        raise BilibiliRequestError("network", "B 站请求未完成", request_url)

    def request_json(self, url: str, headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        response = self.request("GET", url, headers=headers)
        try:
            try:
                payload = response.json()
            except ValueError as exc:
                raise BilibiliRequestError("response", "B 站返回的内容不是 JSON", url) from exc
        finally:
            response.close()

        if not isinstance(payload, dict):
            raise BilibiliRequestError("response", "B 站返回的 JSON 结构无效", url)
        code = int(payload.get("code", 0) or 0)
        if code != 0:
            category = "auth" if code in {-101, -400} else "api"
            message = str(payload.get("message") or "未知接口错误")
            raise BilibiliRequestError(category, f"B 站接口错误 {code}：{message}", url)
        return payload

    def resolve_redirect(self, url: str) -> str:
        response = self.request("GET", url, stream=True)
        try:
            return response.url
        finally:
            response.close()

    def api_url(self, path: str, query: str = "") -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"https://{self.config.api_host}{normalized_path}{'?' + query if query else ''}"

    def wbi_query(self, params: Mapping[str, Any]) -> str:
        values = {str(key): str(value) for key, value in params.items() if value is not None}
        return "&".join(f"{_quote(key)}={_quote(values[key])}" for key in sorted(values))

    def sign_wbi(self, params: Mapping[str, Any]) -> str:
        values = {str(key): value for key, value in params.items() if value is not None}
        values["wts"] = int(time())
        query = self.wbi_query(values)
        return f"{query}&w_rid={md5((query + self._load_wbi_key()).encode('utf-8')).hexdigest()}"

    def _load_wbi_key(self) -> str:
        now = time()
        if self._wbi_key and self._wbi_key_expires_at > now:
            return self._wbi_key

        nav_url = self.api_url("/x/web-interface/nav")
        payload = self.request_json(nav_url)
        data = payload.get("data") or {}
        wbi_img = data.get("wbi_img") or {}
        img_key = _image_key(str(wbi_img.get("img_url", "")))
        sub_key = _image_key(str(wbi_img.get("sub_url", "")))
        raw_key = img_key + sub_key
        if len(raw_key) <= max(WBI_MIXIN_KEY_TABLE):
            raise BilibiliRequestError("auth", "B 站 WBI key 无效", nav_url)
        self._wbi_key = "".join(raw_key[index] for index in WBI_MIXIN_KEY_TABLE[:32])
        self._wbi_key_expires_at = now + 600
        return self._wbi_key


@dataclass(frozen=True)
class BilibiliInput:
    url: str
    kind: str
    bvid: str = ""
    aid: str = ""
    episode_id: str = ""
    season_id: str = ""
    collection_id: str = ""


@dataclass(frozen=True)
class BilibiliPage:
    page: int
    cid: str
    title: str
    duration_ms: int


@dataclass(frozen=True)
class BilibiliPageCollection:
    source_url: str
    input: BilibiliInput
    aid: str
    bvid: str
    title: str
    description: str
    cover_url: str
    pages: tuple[BilibiliPage, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BilibiliTrack:
    url: str
    backup_urls: tuple[str, ...]
    track_type: str
    quality_id: int = 0
    bandwidth: int = 0
    codec_id: int = 0
    codecs: str = ""
    width: int = 0
    height: int = 0
    frame_rate: str = ""
    language: str = ""
    language_name: str = ""
    mime_type: str = ""


@dataclass(frozen=True)
class BilibiliSubtitle:
    url: str
    language: str
    language_name: str
    ai_generated: bool = False


@dataclass(frozen=True)
class BilibiliSelectionPolicy:
    video_codecs: tuple[str, ...] = ("avc", "hevc", "av1")
    maximum_quality_id: int | None = None
    audio_language: str = ""
    prefer_hdr: bool = False


@dataclass(frozen=True)
class BilibiliMediaManifest:
    source_url: str
    input: BilibiliInput
    title: str
    description: str
    cover_url: str
    pages: tuple[BilibiliPage, ...]
    selected_page: BilibiliPage
    video_tracks: tuple[BilibiliTrack, ...]
    audio_tracks: tuple[BilibiliTrack, ...]
    subtitles: tuple[BilibiliSubtitle, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    chapters: tuple[Mapping[str, Any], ...] = ()

    def select_video(self, policy: BilibiliSelectionPolicy | None = None) -> BilibiliTrack | None:
        active_policy = policy or BilibiliSelectionPolicy()
        candidates = [
            track
            for track in self.video_tracks
            if active_policy.maximum_quality_id is None or track.quality_id <= active_policy.maximum_quality_id
        ]
        return max(candidates, key=lambda track: _video_sort_key(track, active_policy), default=None)

    def select_audio(self, policy: BilibiliSelectionPolicy | None = None) -> BilibiliTrack | None:
        active_policy = policy or BilibiliSelectionPolicy()
        candidates = list(self.audio_tracks)
        if active_policy.audio_language:
            localized = [track for track in candidates if track.language == active_policy.audio_language]
            if localized:
                candidates = localized
        return max(candidates, key=lambda track: (track.quality_id, track.bandwidth), default=None)


class BilibiliProvider:
    def __init__(self, session: BilibiliRequestSession | None = None):
        self.session = session or BilibiliRequestSession()

    def describe(self, url: str) -> BilibiliPageCollection:
        normalized_url = self._normalize_url(url)
        parsed_input = parse_bilibili_input(normalized_url)
        if parsed_input.kind in {"episode", "season"}:
            raise BilibiliProviderError("暂不支持番剧下载")
        if parsed_input.kind != "video":
            raise BilibiliProviderError(f"暂不支持解析 B 站输入类型：{parsed_input.kind}")
        view_params = {key: value for key, value in {"bvid": parsed_input.bvid, "aid": parsed_input.aid}.items() if value}
        view_url = self.session.api_url("/x/web-interface/view", self.session.wbi_query(view_params))
        view_payload = self.session.request_json(view_url)
        data = view_payload.get("data") or {}
        pages = _parse_pages(data.get("pages"))
        if not pages:
            fallback_cid = str(data.get("cid") or "")
            if fallback_cid:
                pages = (BilibiliPage(1, fallback_cid, str(data.get("title") or ""), int(data.get("duration", 0) or 0) * 1000),)
        if not pages:
            raise BilibiliProviderError("B 站页面没有可播放分 P")
        aid = str(data.get("aid") or parsed_input.aid)
        bvid = str(data.get("bvid") or parsed_input.bvid)
        return BilibiliPageCollection(
            source_url=normalized_url,
            input=BilibiliInput(normalized_url, "video", bvid=bvid, aid=aid),
            aid=aid,
            bvid=bvid,
            title=str(data.get("title") or ""),
            description=str(data.get("desc") or ""),
            cover_url=str(data.get("pic") or ""),
            pages=pages,
            metadata={
                "owner": data.get("owner") or {},
                "pubdate": data.get("pubdate"),
                "stat": data.get("stat") or {},
                "raw": data,
            },
        )

    def resolve(self, url: str, page: int | None = None) -> BilibiliMediaManifest:
        collection = self.describe(url)
        normalized_url = collection.source_url
        selected_index = (page - 1) if page and page > 0 else _query_page(normalized_url) - 1
        selected_page = collection.pages[min(max(selected_index, 0), len(collection.pages) - 1)]
        aid = collection.aid
        play_params = {
            "avid": aid,
            "cid": selected_page.cid,
            "fnval": 4048,
            "fnver": 0,
            "fourk": 1,
            "from_client": "BROWSER",
            "otype": "json",
            "qn": 0,
            "support_multi_audio": "true",
        }
        play_url = self.session.api_url("/x/player/wbi/playurl", self.session.sign_wbi(play_params))
        play_payload = self.session.request_json(play_url)
        play_data = play_payload.get("data") or {}
        dash = play_data.get("dash") or {}
        video_tracks = tuple(_parse_tracks(dash.get("video"), "video"))
        audio_tracks = tuple(_parse_tracks(dash.get("audio"), "audio"))
        if not video_tracks:
            raise BilibiliProviderError("B 站播放接口没有返回视频轨道")
        subtitles = tuple(_parse_subtitles(collection.metadata.get("raw", {}).get("subtitle"), play_data.get("subtitle")))
        chapters = _parse_chapters(play_data.get("view_points"))
        if not chapters:
            chapters = _parse_chapters(play_data.get("chapters"))
        identity = BilibiliInput(
            url=normalized_url,
            kind="video",
            bvid=collection.bvid,
            aid=aid,
        )
        metadata = {
            **collection.metadata,
            "duration_ms": _duration_ms(play_data, selected_page),
            "page_count": len(collection.pages),
            "cid": selected_page.cid,
            "aid": aid,
            "bvid": collection.bvid,
        }
        return BilibiliMediaManifest(
            source_url=url,
            input=identity,
            title=collection.title or selected_page.title,
            description=collection.description,
            cover_url=collection.cover_url,
            pages=collection.pages,
            selected_page=selected_page,
            video_tracks=video_tracks,
            audio_tracks=audio_tracks,
            subtitles=subtitles,
            chapters=chapters,
            metadata=metadata,
        )

    def _normalize_url(self, url: str) -> str:
        if not is_bilibili_url(url):
            raise BilibiliProviderError("不是 B 站 URL")
        parsed_input = parse_bilibili_input(url)
        return self.session.resolve_redirect(url) if parsed_input.kind == "short" else url


def parse_bilibili_input(url: str) -> BilibiliInput:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return BilibiliInput(url, "unknown")
    path = parsed.path or ""
    lowered_path = path.lower()
    if (parsed.hostname or "").lower().endswith("b23.tv") or lowered_path.startswith("/s/"):
        return BilibiliInput(url, "short")
    bvid_match = re.search(r"(?i)(BV[0-9A-Za-z]+)", path)
    aid_match = re.search(r"(?i)(?:^|/)av(\d+)", path)
    if bvid_match or aid_match:
        return BilibiliInput(url, "video", bvid_match.group(1) if bvid_match else "", aid_match.group(1) if aid_match else "")
    episode_match = re.search(r"(?i)/(?:bangumi/play/)?ep(\d+)", path)
    if episode_match:
        return BilibiliInput(url, "episode", episode_id=episode_match.group(1))
    season_match = re.search(r"(?i)/(?:bangumi/play/)?ss(\d+)", path)
    if season_match:
        return BilibiliInput(url, "season", season_id=season_match.group(1))
    if "medialist/play" in lowered_path or "collectiondetail" in lowered_path:
        collection_id = _query_value(parsed.query, "business_id") or _query_value(parsed.query, "sid")
        return BilibiliInput(url, "collection", collection_id=collection_id)
    if "seriesdetail" in lowered_path:
        return BilibiliInput(url, "series", collection_id=_query_value(parsed.query, "sid"))
    if "cheese" in lowered_path or "course" in lowered_path:
        return BilibiliInput(url, "course")
    return BilibiliInput(url, "unknown")


def _parse_pages(raw_pages: Any) -> tuple[BilibiliPage, ...]:
    if not isinstance(raw_pages, list):
        return ()
    pages: list[BilibiliPage] = []
    for index, item in enumerate(raw_pages, start=1):
        if not isinstance(item, dict):
            continue
        cid = str(item.get("cid") or "")
        if not cid:
            continue
        pages.append(BilibiliPage(int(item.get("page") or index), cid, str(item.get("part") or ""), int(item.get("duration", 0) or 0) * 1000))
    return tuple(pages)


def _parse_tracks(raw_tracks: Any, track_type: str) -> list[BilibiliTrack]:
    if not isinstance(raw_tracks, list):
        return []
    tracks: list[BilibiliTrack] = []
    for item in raw_tracks:
        if not isinstance(item, dict):
            continue
        url = str(item.get("base_url") or item.get("baseUrl") or "")
        if not url:
            continue
        backups = item.get("backup_url") or item.get("backupUrl") or []
        backup_urls = tuple(str(value) for value in backups if value) if isinstance(backups, list) else ()
        tracks.append(
            BilibiliTrack(
                url=url,
                backup_urls=backup_urls,
                track_type=track_type,
                quality_id=int(item.get("id", 0) or 0),
                bandwidth=int(item.get("bandwidth", 0) or 0),
                codec_id=int(item.get("codecid", 0) or 0),
                codecs=str(item.get("codecs") or ""),
                width=int(item.get("width", 0) or 0),
                height=int(item.get("height", 0) or 0),
                frame_rate=str(item.get("frame_rate") or ""),
                language=str(item.get("lang") or item.get("language") or ""),
                language_name=str(item.get("lang_name") or item.get("language_name") or ""),
                mime_type="audio/mp4" if track_type == "audio" else "video/mp4",
            ),
        )
    return tracks


def _parse_subtitles(*sources: Any) -> list[BilibiliSubtitle]:
    subtitles: list[BilibiliSubtitle] = []
    for source in sources:
        items = source.get("list") if isinstance(source, dict) else source
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("subtitle_url") or item.get("url") or "")
            if url.startswith("//"):
                url = f"https:{url}"
            if not url:
                continue
            subtitles.append(
                BilibiliSubtitle(
                    url=url,
                    language=str(item.get("lan") or item.get("language") or ""),
                    language_name=str(item.get("lan_doc") or item.get("language_name") or ""),
                    ai_generated=bool(item.get("ai_status") or item.get("ai_type")),
                ),
            )
    return subtitles


def _parse_chapters(source: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(source, list):
        return ()
    chapters: list[Mapping[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        start_ms = item.get("start_ms", item.get("from", item.get("start", 0)))
        end_ms = item.get("end_ms", item.get("to", item.get("end", 0)))
        try:
            start_value = float(start_ms or 0)
            end_value = float(end_ms or 0)
        except (TypeError, ValueError):
            continue
        if start_value < 10000 and end_value < 10000:
            start_value *= 1000
            end_value *= 1000
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title or end_value <= start_value:
            continue
        chapters.append({"start_ms": int(start_value), "end_ms": int(end_value), "title": title})
    return tuple(chapters)


def _video_sort_key(track: BilibiliTrack, policy: BilibiliSelectionPolicy) -> tuple[int, int, int, int]:
    codec_name = _codec_name(track)
    try:
        codec_rank = len(policy.video_codecs) - policy.video_codecs.index(codec_name)
    except ValueError:
        codec_rank = 0
    hdr_rank = 1 if policy.prefer_hdr and "hdr" in track.codecs.lower() else 0
    return codec_rank, hdr_rank, track.quality_id, track.bandwidth


def _codec_name(track: BilibiliTrack) -> str:
    if track.codec_id == 7 or "avc" in track.codecs.lower():
        return "avc"
    if track.codec_id == 12 or "hev" in track.codecs.lower() or "hvc" in track.codecs.lower():
        return "hevc"
    if track.codec_id == 13 or "av01" in track.codecs.lower():
        return "av1"
    return "unknown"


def _duration_ms(play_data: Mapping[str, Any], selected_page: BilibiliPage) -> int:
    if play_data.get("timelength"):
        return int(play_data["timelength"])
    if play_data.get("duration"):
        return int(play_data["duration"]) * 1000
    return selected_page.duration_ms


def _query_page(url: str) -> int:
    return max(1, int(_query_value(urlsplit(url).query, "p") or "1"))


def _query_value(query: str, key: str) -> str:
    for item in query.split("&"):
        name, separator, value = item.partition("=")
        if name == key and separator:
            return value
    return ""


def _quote(value: Any) -> str:
    return quote(str(value), safe="").replace("!", "%21").replace("'", "%27").replace("(", "%28").replace(")", "%29").replace("*", "%2A")


def _image_key(url: str) -> str:
    return url.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _retry_delay(attempt: int) -> float:
    return min(2.0, 0.25 * (2**attempt))


def _http_error_category(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth"
    if status_code == 429:
        return "rate_limit"
    return "http"


def _is_bilivideo_host(host: str | None) -> bool:
    normalized = (host or "").lower().rstrip(".")
    return normalized == "bilivideo.com" or normalized.endswith(".bilivideo.com") or normalized == "bilivideo.cn" or normalized.endswith(".bilivideo.cn")


def _keep_https_for_host(parsed) -> bool:
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        port = None
    return host.endswith(".mcdn.bilivideo.cn") and port is not None


def _uses_android_platform(url: str) -> bool:
    lowered = url.lower()
    return "platform=android_tv_yst" in lowered or "platform=android" in lowered


def _has_header(headers: Mapping[str, str], name: str) -> bool:
    return any(key.lower() == name.lower() for key in headers)
