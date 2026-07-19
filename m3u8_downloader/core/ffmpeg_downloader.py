from __future__ import annotations

import subprocess
from pathlib import Path

from .bilibili import prepare_bilibili_request


class FFmpegDownloadError(RuntimeError):
    """Raised when FFmpeg cannot save the input media."""


def download_with_ffmpeg(
    url: str,
    output_path: Path,
    headers: dict[str, str] | None = None,
    ffmpeg_path: str = "ffmpeg",
    bilibili_compat: bool = False,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request_url, request_headers = prepare_bilibili_request(url, headers, bilibili_compat)
    command = [ffmpeg_path, "-y"]
    header_block = _headers_for_ffmpeg(request_headers)
    if header_block:
        command.extend(["-headers", header_block])
    command.extend(["-i", request_url, "-c", "copy", str(output_path)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FFmpegDownloadError(result.stderr.strip() or "ffmpeg download failed")
    return True


def _headers_for_ffmpeg(headers: dict[str, str]) -> str:
    return "".join(f"{name}: {value}\r\n" for name, value in headers.items() if value)
