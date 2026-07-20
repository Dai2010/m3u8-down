from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import requests

from .bilibili import prepare_bilibili_request, throttle_bilibili_request


class MediaKind(str, Enum):
    HLS = "hls"
    DASH = "dash"
    SMOOTH = "smooth"
    RTSP = "rtsp"
    PROGRESSIVE = "progressive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MediaInfo:
    kind: MediaKind
    source: str = "unknown"
    content_type: str = ""

    @property
    def display_name(self) -> str:
        return {
            MediaKind.HLS: "HLS/m3u8",
            MediaKind.DASH: "MPEG-DASH/mpd",
            MediaKind.SMOOTH: "Smooth Streaming",
            MediaKind.RTSP: "RTSP stream",
            MediaKind.PROGRESSIVE: "direct media",
            MediaKind.UNKNOWN: "unknown media",
        }[self.kind]


PROGRESSIVE_EXTENSIONS = {
    ".mp4",
    ".m4s",
    ".m4v",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
    ".avi",
    ".ts",
    ".m2ts",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wav",
}


def detect_media_type(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
    bilibili_compat: bool = False,
) -> MediaInfo:
    info = detect_media_type_from_url(url)
    if info.kind != MediaKind.UNKNOWN:
        return info

    request_url, request_headers = prepare_bilibili_request(url, headers, bilibili_compat)
    info = _detect_with_head(request_url, request_headers, timeout)
    if info.kind != MediaKind.UNKNOWN:
        return info
    return _detect_with_preview_get(request_url, request_headers, timeout)


def detect_media_type_from_url(url: str) -> MediaInfo:
    parsed = urlparse(url)
    if parsed.scheme.lower() == "rtsp":
        return MediaInfo(MediaKind.RTSP, "url")
    path = parsed.path.lower()
    if path.endswith((".m3u8", ".m3u")):
        return MediaInfo(MediaKind.HLS, "url")
    if path.endswith(".mpd"):
        return MediaInfo(MediaKind.DASH, "url")
    if path.endswith("/manifest") and ".ism" in path:
        return MediaInfo(MediaKind.SMOOTH, "url")
    if any(path.endswith(extension) for extension in PROGRESSIVE_EXTENSIONS):
        return MediaInfo(MediaKind.PROGRESSIVE, "url")
    return MediaInfo(MediaKind.UNKNOWN)


def detect_media_type_from_content_type(content_type: str) -> MediaInfo:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized in {"application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl"}:
        return MediaInfo(MediaKind.HLS, "content-type", content_type)
    if normalized == "application/dash+xml":
        return MediaInfo(MediaKind.DASH, "content-type", content_type)
    if normalized == "application/vnd.ms-sstr+xml":
        return MediaInfo(MediaKind.SMOOTH, "content-type", content_type)
    if normalized in {"application/mp4", "application/fmp4"} or normalized.startswith(("video/", "audio/")):
        return MediaInfo(MediaKind.PROGRESSIVE, "content-type", content_type)
    return MediaInfo(MediaKind.UNKNOWN, "content-type", content_type)


def detect_media_type_from_body(body: str) -> MediaInfo:
    preview = body.lstrip("\ufeff\n\r\t ")
    if preview.startswith("#EXTM3U"):
        return MediaInfo(MediaKind.HLS, "body")
    if preview.startswith("<MPD") or "<MPD" in preview[:256]:
        return MediaInfo(MediaKind.DASH, "body")
    if preview.startswith("<SmoothStreamingMedia") or "<SmoothStreamingMedia" in preview[:256]:
        return MediaInfo(MediaKind.SMOOTH, "body")
    return MediaInfo(MediaKind.UNKNOWN, "body")


def detect_media_type_from_bytes(body: bytes, content_type: str = "") -> MediaInfo:
    text_info = detect_media_type_from_body(body.decode("utf-8", errors="ignore"))
    if text_info.kind != MediaKind.UNKNOWN:
        return text_info
    if _looks_like_progressive_bytes(body):
        return MediaInfo(MediaKind.PROGRESSIVE, "body", content_type)
    return MediaInfo(MediaKind.UNKNOWN, "body", content_type)


def _looks_like_progressive_bytes(body: bytes) -> bool:
    if len(body) >= 8 and body[4:8] == b"ftyp":
        return True
    if body.startswith((b"\x1a\x45\xdf\xa3", b"OggS", b"RIFF", b"ID3")):
        return True
    if len(body) >= 2 and body[0] == 0xFF and body[1] & 0xE0 == 0xE0:
        return True
    if len(body) >= 2 and body[0] == 0xFF and body[1] & 0xF6 == 0xF0:
        return True
    return any(offset < len(body) and body[offset] == 0x47 for offset in (0, 188, 376))


def _detect_with_head(url: str, headers: dict[str, str], timeout: int) -> MediaInfo:
    try:
        throttle_bilibili_request(url)
        with requests.head(url, headers=headers, allow_redirects=True, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
    except requests.RequestException:
        return MediaInfo(MediaKind.UNKNOWN)
    return detect_media_type_from_content_type(content_type)


def _detect_with_preview_get(url: str, headers: dict[str, str], timeout: int) -> MediaInfo:
    request_headers = dict(headers)
    request_headers.setdefault("Range", "bytes=0-4095")
    try:
        throttle_bilibili_request(url)
        with requests.get(url, headers=request_headers, stream=True, allow_redirects=True, timeout=timeout) as response:
            content_type_info = detect_media_type_from_content_type(response.headers.get("Content-Type", ""))
            if content_type_info.kind != MediaKind.UNKNOWN:
                return content_type_info
            chunk = next(response.iter_content(chunk_size=4096), b"")
    except requests.RequestException:
        return MediaInfo(MediaKind.UNKNOWN)
    except StopIteration:
        chunk = b""
    return detect_media_type_from_bytes(chunk, response.headers.get("Content-Type", ""))
