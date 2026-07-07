from __future__ import annotations

import re

from .parser import Playlist, Segment


def is_ad_segment(segment: Segment, keywords: list[str], use_regex: bool = False) -> bool:
    haystack = f"{segment.url}\n{segment.title}"
    if use_regex:
        return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in keywords)
    lowered = haystack.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def filter_playlist(playlist: Playlist, keywords: list[str], use_regex: bool = False) -> Playlist:
    if not keywords or playlist.is_master:
        return playlist
    segments = [segment for segment in playlist.segments if not is_ad_segment(segment, keywords, use_regex)]
    return playlist.with_segments(segments)
