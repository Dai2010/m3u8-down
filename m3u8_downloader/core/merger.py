from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Mapping


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


def merge_bilibili_tracks(
    video_path: Path,
    audio_path: Path | None,
    output_path: Path,
    subtitles: list[tuple[Path, str]] | None = None,
    chapters: tuple[Mapping[str, object], ...] = (),
    metadata: Mapping[str, object] | None = None,
    ffmpeg_path: str = "ffmpeg",
) -> bool:
    if not video_path.exists():
        raise MergeError("B 站视频轨道不存在")
    if audio_path is not None and not audio_path.exists():
        raise MergeError("B 站音频轨道不存在")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subtitle_items = subtitles or []
    chapter_path: Path | None = None
    command = [ffmpeg_path, "-y", "-i", str(video_path)]
    subtitle_start = 1
    if audio_path is not None:
        command.extend(["-i", str(audio_path)])
        subtitle_start += 1
    for subtitle_path, _language in subtitle_items:
        command.extend(["-i", str(subtitle_path)])
    if chapters:
        chapter_file = tempfile.NamedTemporaryFile("w", suffix=".ffmeta", delete=False, encoding="utf-8")
        chapter_path = Path(chapter_file.name)
        try:
            chapter_file.write(";FFMETADATA1\n")
            for chapter in chapters:
                start = int(chapter.get("start_ms", 0) or 0)
                end = int(chapter.get("end_ms", 0) or 0)
                title = str(chapter.get("title", ""))
                if end <= start or not title:
                    continue
                chapter_file.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={start}\nEND={end}\ntitle={title}\n")
        finally:
            chapter_file.close()
        command.extend(["-f", "ffmetadata", "-i", str(chapter_path)])
        chapter_input_index = subtitle_start + len(subtitle_items)
    else:
        chapter_input_index = -1

    command.extend(["-map", "0:v:0"])
    if audio_path is not None:
        command.extend(["-map", "1:a:0"])
    for subtitle_index, (_subtitle_path, language) in enumerate(subtitle_items):
        input_index = subtitle_start + subtitle_index
        command.extend(["-map", f"{input_index}:s:0", f"-metadata:s:s:{subtitle_index}", f"language={language}"])
    command.extend(["-c:v", "copy"])
    if audio_path is not None:
        command.extend(["-c:a", "copy"])
    if subtitle_items:
        command.extend(["-c:s", "mov_text"])
    title = str((metadata or {}).get("title") or "")
    description = str((metadata or {}).get("description") or "")
    if title:
        command.extend(["-metadata", f"title={title}"])
    if description:
        command.extend(["-metadata", f"comment={description}"])
    if chapter_input_index >= 0:
        command.extend(["-map_chapters", str(chapter_input_index)])
    command.append(str(output_path))
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise MergeError(result.stderr.strip() or "B 站音视频合并失败")
        return True
    finally:
        if chapter_path is not None:
            chapter_path.unlink(missing_ok=True)
