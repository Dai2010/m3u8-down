from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional
from urllib.parse import urljoin


class ParseError(ValueError):
    """Raised when playlist content is not a valid m3u8 document."""


class UnsupportedTag(RuntimeError):
    """Marker for tags intentionally ignored by the parser."""


@dataclass(frozen=True)
class Key:
    method: str
    uri: Optional[str] = None
    iv: Optional[str] = None


@dataclass(frozen=True)
class Segment:
    duration: float
    url: str
    title: str = ""
    discontinuity: bool = False
    key: Optional[Key] = None


@dataclass(frozen=True)
class Variant:
    bandwidth: int = 0
    resolution: str = ""
    codecs: str = ""
    url: str = ""


@dataclass(frozen=True)
class Playlist:
    version: int = 0
    target_duration: float = 0
    media_sequence: int = 0
    playlist_type: str = ""
    segments: list[Segment] = field(default_factory=list)
    is_master: bool = False
    variants: list[Variant] = field(default_factory=list)

    def with_segments(self, segments: list[Segment]) -> "Playlist":
        return replace(self, segments=segments)

    def best_variant(self) -> Optional[Variant]:
        if not self.variants:
            return None
        return max(self.variants, key=lambda variant: variant.bandwidth)


def resolve_url(base: str, relative: str) -> str:
    return urljoin(base, relative)


def parse_playlist(content: str, base_url: str = "") -> Playlist:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines or lines[0] != "#EXTM3U":
        raise ParseError("playlist must start with #EXTM3U")

    version = 0
    target_duration = 0.0
    media_sequence = 0
    playlist_type = ""
    segments: list[Segment] = []
    variants: list[Variant] = []
    pending_duration: Optional[float] = None
    pending_title = ""
    pending_discontinuity = False
    pending_variant: Optional[dict[str, str]] = None
    current_key: Optional[Key] = None

    for line in lines[1:]:
        if line.startswith("#EXT-X-VERSION:"):
            version = _parse_int_value(line, "#EXT-X-VERSION:")
        elif line.startswith("#EXT-X-TARGETDURATION:"):
            target_duration = _parse_float_value(line, "#EXT-X-TARGETDURATION:")
        elif line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            media_sequence = _parse_int_value(line, "#EXT-X-MEDIA-SEQUENCE:")
        elif line.startswith("#EXT-X-PLAYLIST-TYPE:"):
            playlist_type = line.split(":", 1)[1].strip().upper()
        elif line.startswith("#EXT-X-KEY:"):
            current_key = _parse_key(line.split(":", 1)[1], base_url)
        elif line == "#EXT-X-DISCONTINUITY":
            pending_discontinuity = True
        elif line.startswith("#EXT-X-STREAM-INF:"):
            pending_variant = _parse_attributes(line.split(":", 1)[1])
        elif line.startswith("#EXTINF:"):
            duration_title = line.split(":", 1)[1]
            duration, _, title = duration_title.partition(",")
            try:
                pending_duration = float(duration)
            except ValueError as exc:
                raise ParseError(f"invalid segment duration: {duration}") from exc
            pending_title = title.strip()
        elif line.startswith("#"):
            continue
        elif pending_variant is not None:
            variants.append(
                Variant(
                    bandwidth=int(pending_variant.get("BANDWIDTH", "0") or 0),
                    resolution=pending_variant.get("RESOLUTION", ""),
                    codecs=pending_variant.get("CODECS", ""),
                    url=resolve_url(base_url, line),
                )
            )
            pending_variant = None
        elif pending_duration is not None:
            segments.append(
                Segment(
                    duration=pending_duration,
                    url=resolve_url(base_url, line),
                    title=pending_title,
                    discontinuity=pending_discontinuity,
                    key=current_key,
                )
            )
            pending_duration = None
            pending_title = ""
            pending_discontinuity = False
        else:
            raise ParseError(f"URI without matching tag: {line}")

    return Playlist(
        version=version,
        target_duration=target_duration,
        media_sequence=media_sequence,
        playlist_type=playlist_type,
        segments=segments,
        is_master=bool(variants),
        variants=variants,
    )


def playlist_to_m3u8(playlist: Playlist) -> str:
    lines = ["#EXTM3U"]
    if playlist.version:
        lines.append(f"#EXT-X-VERSION:{playlist.version}")

    if playlist.is_master:
        for variant in playlist.variants:
            attrs = [f"BANDWIDTH={variant.bandwidth}"] if variant.bandwidth else []
            if variant.resolution:
                attrs.append(f"RESOLUTION={variant.resolution}")
            if variant.codecs:
                attrs.append(f'CODECS="{variant.codecs}"')
            lines.append(f"#EXT-X-STREAM-INF:{','.join(attrs)}")
            lines.append(variant.url)
        return "\n".join(lines) + "\n"

    if playlist.target_duration:
        lines.append(f"#EXT-X-TARGETDURATION:{_format_number(playlist.target_duration)}")
    if playlist.media_sequence:
        lines.append(f"#EXT-X-MEDIA-SEQUENCE:{playlist.media_sequence}")
    if playlist.playlist_type:
        lines.append(f"#EXT-X-PLAYLIST-TYPE:{playlist.playlist_type}")

    current_key: Optional[Key] = None
    for segment in playlist.segments:
        if segment.key != current_key:
            current_key = segment.key
            if current_key:
                attrs = [f"METHOD={current_key.method}"]
                if current_key.uri:
                    attrs.append(f'URI="{current_key.uri}"')
                if current_key.iv:
                    attrs.append(f"IV={current_key.iv}")
                lines.append(f"#EXT-X-KEY:{','.join(attrs)}")
        if segment.discontinuity:
            lines.append("#EXT-X-DISCONTINUITY")
        lines.append(f"#EXTINF:{_format_number(segment.duration)},{segment.title}")
        lines.append(segment.url)
    lines.append("#EXT-X-ENDLIST")
    return "\n".join(lines) + "\n"


def _parse_int_value(line: str, prefix: str) -> int:
    value = line.removeprefix(prefix).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise ParseError(f"invalid integer value: {value}") from exc


def _parse_float_value(line: str, prefix: str) -> float:
    value = line.removeprefix(prefix).strip()
    try:
        return float(value)
    except ValueError as exc:
        raise ParseError(f"invalid float value: {value}") from exc


def _parse_key(value: str, base_url: str) -> Key:
    attrs = _parse_attributes(value)
    uri = attrs.get("URI")
    return Key(method=attrs.get("METHOD", ""), uri=resolve_url(base_url, uri) if uri else None, iv=attrs.get("IV"))


def _parse_attributes(value: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for item in _split_attribute_list(value):
        key, sep, raw = item.partition("=")
        if sep:
            attrs[key.strip().upper()] = raw.strip().strip('"')
    return attrs


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _split_attribute_list(value: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    in_quote = False
    for char in value:
        if char == '"':
            in_quote = not in_quote
        if char == "," and not in_quote:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        items.append("".join(current).strip())
    return items
