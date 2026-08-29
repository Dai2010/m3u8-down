from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path


def expand_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for value in values:
        name, sep, header_value = value.partition(":")
        if sep and name.strip():
            headers[name.strip()] = header_value.strip()
    return headers


def setup_logging() -> None:
    log_dir = Path.home() / ".cache" / "m3u8-downloader" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "m3u8-downloader.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def resolve_ffmpeg(ffmpeg_path: str = "ffmpeg") -> str:
    if ffmpeg_path != "ffmpeg":
        return ffmpeg_path

    bundled_path = _bundled_ffmpeg_path()
    return str(bundled_path) if bundled_path else ffmpeg_path


def require_ffmpeg(ffmpeg_path: str = "ffmpeg") -> None:
    resolved_path = resolve_ffmpeg(ffmpeg_path)
    if Path(resolved_path).is_file() or shutil.which(resolved_path) is not None:
        return
    raise RuntimeError("ffmpeg not found; install FFmpeg or use the packaged installer")


def _bundled_ffmpeg_path() -> Path | None:
    candidates = [Path(sys.executable).resolve().parent / "ffmpeg.exe"]
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(Path(meipass) / "ffmpeg.exe")
    return next((candidate for candidate in candidates if candidate.is_file()), None)
