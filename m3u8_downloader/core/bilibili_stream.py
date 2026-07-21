from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .bilibili import (
    BilibiliMediaManifest,
    BilibiliProvider,
    BilibiliRequestConfig,
    BilibiliRequestSession,
    BilibiliSelectionPolicy,
    BilibiliTrack,
    is_bilibili_page_url,
)


@dataclass(frozen=True)
class BilibiliPlayback:
    manifest: BilibiliMediaManifest
    video: BilibiliTrack
    audio: BilibiliTrack | None


def resolve_bilibili_playback(
    url: str,
    headers: Mapping[str, str] | None = None,
    maximum_quality_id: int | None = None,
    http: Any | None = None,
) -> BilibiliPlayback:
    if not is_bilibili_page_url(url):
        raise ValueError("不是可播放的 B 站视频页面")
    request_headers = dict(headers or {})
    cookie = next((value for name, value in request_headers.items() if name.lower() == "cookie"), "")
    session = BilibiliRequestSession(
        BilibiliRequestConfig(headers=request_headers, cookie=cookie),
        http=http,
    )
    manifest = BilibiliProvider(session).resolve(url)
    policy = BilibiliSelectionPolicy(maximum_quality_id=maximum_quality_id)
    video = manifest.select_video(policy)
    if video is None:
        raise RuntimeError("B 站页面没有可播放的视频轨道")
    return BilibiliPlayback(manifest, video, manifest.select_audio(policy))
