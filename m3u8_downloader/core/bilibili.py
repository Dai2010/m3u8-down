from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


BILIBILI_HOST_SUFFIXES = ("bilibili.com", "bilibili.tv", "bilivideo.com", "bilivideo.cn")


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
) -> tuple[str, dict[str, str]]:
    request_headers = {key: value for key, value in (headers or {}).items() if value}
    if not enabled and not is_bilibili_url(url):
        return url, request_headers

    if not _has_header(request_headers, "User-Agent"):
        request_headers["User-Agent"] = "Mozilla/5.0"
    if not _uses_android_platform(url) and not _has_header(request_headers, "Referer"):
        request_headers["Referer"] = "https://www.bilibili.com"

    parsed = urlsplit(url)
    if parsed.scheme.lower() == "https" and _is_bilivideo_host(parsed.hostname) and not _keep_https_for_host(parsed):
        return urlunsplit(("http", parsed.netloc, parsed.path, parsed.query, parsed.fragment)), request_headers
    return url, request_headers


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


def _has_header(headers: dict[str, str], name: str) -> bool:
    return any(key.lower() == name.lower() for key in headers)
