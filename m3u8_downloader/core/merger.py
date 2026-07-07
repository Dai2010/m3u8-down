from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class MergeError(RuntimeError):
    """Raised when ffmpeg fails to merge downloaded segments."""


def merge_to_mp4(ts_files: list[Path], output_path: Path, ffmpeg_path: str = "ffmpeg") -> bool:
    if not ts_files:
        raise MergeError("no ts files to merge")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as list_file:
        list_path = Path(list_file.name)
        for ts_file in ts_files:
            escaped = str(ts_file.resolve()).replace("'", "'\\''")
            list_file.write(f"file '{escaped}'\n")

    try:
        command = [
            ffmpeg_path,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            str(output_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise MergeError(result.stderr.strip() or "ffmpeg merge failed")
        return True
    finally:
        list_path.unlink(missing_ok=True)
