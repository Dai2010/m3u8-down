from __future__ import annotations

import logging
import shutil
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


def require_ffmpeg(ffmpeg_path: str = "ffmpeg") -> None:
    if shutil.which(ffmpeg_path) is None:
        raise RuntimeError("ffmpeg not found; install it with: sudo apt install ffmpeg")
