from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
from typing import Callable, Mapping

from .bilibili import (
    BilibiliMediaManifest,
    BilibiliProvider,
    BilibiliRequestSession,
    BilibiliSelectionPolicy,
    BilibiliSubtitle,
    BilibiliTrack,
)
from .direct_downloader import download_direct_media
from .merger import merge_bilibili_tracks


ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


@dataclass(frozen=True)
class BilibiliDownloadOptions:
    selection: BilibiliSelectionPolicy = BilibiliSelectionPolicy()
    threads: int = 4
    retries: int = 3
    save_subtitles: bool = True
    save_cover: bool = True
    save_danmaku: bool = False
    save_chapters: bool = True
    save_info: bool = True
    keep_intermediates: bool = False
    ffmpeg_path: str = "ffmpeg"


@dataclass(frozen=True)
class BilibiliDownloadResult:
    output_path: Path
    video_path: Path
    audio_path: Path | None
    subtitle_paths: tuple[Path, ...]
    cover_path: Path | None
    danmaku_path: Path | None
    info_path: Path | None


class BilibiliDownloadError(RuntimeError):
    pass


def download_bilibili_manifest(
    manifest: BilibiliMediaManifest,
    output_path: Path,
    session: BilibiliRequestSession,
    options: BilibiliDownloadOptions | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> BilibiliDownloadResult:
    active_options = options or BilibiliDownloadOptions()
    video = manifest.select_video(active_options.selection)
    audio = manifest.select_audio(active_options.selection)
    if video is None:
        raise BilibiliDownloadError("B 站没有符合清晰度和编码条件的视频轨道")
    work_dir = output_path.with_name(f".{output_path.stem}.bilibili")
    work_dir.mkdir(parents=True, exist_ok=True)
    video_path = work_dir / "video.m4s"
    audio_path = work_dir / "audio.m4s" if audio is not None else None
    tracks = [("video", video, video_path), ("audio", audio, audio_path)]
    tracks = [(name, track, path) for name, track, path in tracks if track is not None and path is not None]
    progress_total = len(tracks)
    progress_done = 0

    def report(message: str) -> None:
        if progress_callback:
            progress_callback(progress_done, progress_total, message)

    try:
        with ThreadPoolExecutor(max_workers=min(max(1, active_options.threads), len(tracks))) as executor:
            futures = {
                executor.submit(
                    _download_track,
                    track,
                    path,
                    session,
                    active_options,
                    cancel_callback,
                ): name
                for name, track, path in tracks
            }
            failures: list[str] = []
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001 - combine both track failures.
                    failures.append(f"{name}: {exc}")
                progress_done += 1
                report(f"已下载 {progress_done}/{progress_total} 个 B 站轨道")
            if failures:
                raise BilibiliDownloadError("；".join(failures))
        if cancel_callback and cancel_callback():
            raise BilibiliDownloadError("下载已取消，已保留临时文件以便继续")

        subtitle_paths = _download_subtitles(manifest.subtitles, output_path, session, active_options) if active_options.save_subtitles else []
        cover_path = _download_cover(manifest.cover_url, output_path, session) if active_options.save_cover else None
        danmaku_path = _download_danmaku(manifest, output_path, session) if active_options.save_danmaku else None
        info_path = _write_info(manifest, output_path) if active_options.save_info else None
        subtitle_inputs = [(path, language) for path, language in subtitle_paths]
        report("正在合并视频、音频和附件")
        merge_bilibili_tracks(
            video_path,
            audio_path,
            output_path,
            subtitles=subtitle_inputs,
            chapters=manifest.chapters if active_options.save_chapters else (),
            metadata={"title": manifest.title, "description": manifest.description},
            ffmpeg_path=active_options.ffmpeg_path,
        )
        if not active_options.keep_intermediates:
            shutil.rmtree(work_dir, ignore_errors=True)
        if progress_callback:
            progress_callback(progress_total, progress_total, f"已保存 {output_path}")
        return BilibiliDownloadResult(
            output_path=output_path,
            video_path=video_path,
            audio_path=audio_path,
            subtitle_paths=tuple(path for path, _language in subtitle_paths),
            cover_path=cover_path,
            danmaku_path=danmaku_path,
            info_path=info_path,
        )
    except Exception:
        if not active_options.keep_intermediates:
            work_dir.mkdir(parents=True, exist_ok=True)
        raise


def download_bilibili_url(
    url: str,
    output_path: Path,
    session: BilibiliRequestSession,
    page: int | None = None,
    options: BilibiliDownloadOptions | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> BilibiliDownloadResult:
    manifest = BilibiliProvider(session).resolve(url, page=page)
    return download_bilibili_manifest(manifest, output_path, session, options, progress_callback, cancel_callback)


def _download_track(
    track: BilibiliTrack,
    output_path: Path,
    session: BilibiliRequestSession,
    options: BilibiliDownloadOptions,
    cancel_callback: CancelCallback | None,
) -> None:
    headers = session.config.headers_for(track.url)
    download_direct_media(
        track.url,
        output_path,
        headers=headers,
        timeout=int(session.config.timeout),
        cancel_callback=cancel_callback,
        bilibili_compat=True,
        retries=options.retries,
        backup_urls=track.backup_urls,
    )


def _download_subtitles(
    subtitles: tuple[BilibiliSubtitle, ...],
    output_path: Path,
    session: BilibiliRequestSession,
    options: BilibiliDownloadOptions,
) -> list[tuple[Path, str]]:
    saved: list[tuple[Path, str]] = []
    for index, subtitle in enumerate(subtitles, start=1):
        try:
            response = session.request("GET", subtitle.url)
            try:
                payload = response.json()
            finally:
                response.close()
            path = output_path.with_name(f"{output_path.stem}.{_safe_name(subtitle.language or str(index))}.srt")
            path.write_text(_bcc_to_srt(payload), encoding="utf-8")
            saved.append((path, subtitle.language or "und"))
        except Exception:
            continue
    return saved


def _download_cover(url: str, output_path: Path, session: BilibiliRequestSession) -> Path | None:
    if not url:
        return None
    try:
        response = session.request("GET", url, headers={"Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"})
        try:
            content = response.content
            content_type = response.headers.get("Content-Type", "")
        finally:
            response.close()
        extension = ".png" if "png" in content_type else ".jpg"
        path = output_path.with_name(f"{output_path.stem}.cover{extension}")
        path.write_bytes(content)
        return path
    except Exception:
        return None


def _download_danmaku(
    manifest: BilibiliMediaManifest,
    output_path: Path,
    session: BilibiliRequestSession,
) -> Path | None:
    cid = str(manifest.metadata.get("cid") or manifest.selected_page.cid)
    if not cid:
        return None
    url = session.api_url("/x/v1/dm/list.so", f"oid={cid}")
    try:
        response = session.request("GET", url)
        try:
            content = response.content
        finally:
            response.close()
        path = output_path.with_name(f"{output_path.stem}.danmaku.xml")
        path.write_bytes(content)
        return path
    except Exception:
        return None


def _write_info(manifest: BilibiliMediaManifest, output_path: Path) -> Path:
    path = output_path.with_name(f"{output_path.stem}.info.json")
    payload = {
        "title": manifest.title,
        "description": manifest.description,
        "cover_url": manifest.cover_url,
        "source_url": manifest.source_url,
        "bvid": manifest.input.bvid,
        "aid": manifest.input.aid,
        "page": manifest.selected_page.page,
        "cid": manifest.selected_page.cid,
        "pages": [page.__dict__ for page in manifest.pages],
        "chapters": list(manifest.chapters),
        "metadata": _json_safe(manifest.metadata),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _bcc_to_srt(payload: object) -> str:
    body = payload.get("body", []) if isinstance(payload, dict) else []
    rows: list[str] = []
    for index, item in enumerate(body, start=1):
        if not isinstance(item, dict):
            continue
        start = float(item.get("from", 0) or 0)
        end = float(item.get("to", start) or start)
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        rows.append(f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{content}\n")
    return "\n".join(rows) + ("\n" if rows else "")


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, int(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_value, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_value:02d},{milliseconds:03d}"


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("._")
    return normalized or "und"


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items() if key != "raw"}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
