from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

from .config.manager import load_config
from .core.downloader import Downloader
from .core.ffmpeg_downloader import download_with_ffmpeg
from .core.filter import filter_playlist
from .core.media_type import MediaKind, detect_media_type
from .core.merger import merge_to_mp4
from .core.parser import Playlist, parse_playlist, playlist_to_m3u8
from .core.utils import expand_path, parse_headers, require_ffmpeg, setup_logging


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(prog="m3u8-downloader")
    parser.add_argument("url", nargs="?", help="media URL; omit to open the TUI")
    parser.add_argument("-o", "--output", default="", help="output media path")
    parser.add_argument("--work-dir", default="", help="directory used for downloaded ts segments")
    parser.add_argument("--header", action="append", default=[], help="HTTP header, e.g. 'Referer: https://example.com'")
    parser.add_argument("--keyword", action="append", default=[], help="ad segment keyword")
    parser.add_argument("--regex", action="store_true", help="treat keywords as regular expressions")
    parser.add_argument("--threads", type=int, default=0, help="download worker count")
    parser.add_argument("--variant", type=int, default=-1, help="master playlist variant index; defaults to highest bandwidth")
    parser.add_argument("--dump-filtered", default="", help="write filtered m3u8 content to this path")
    parser.add_argument("--keep-segments", action="store_true", help="keep downloaded ts files after merge")
    parser.add_argument("--tui", action="store_true", help="open the terminal UI")
    args = parser.parse_args()

    if args.tui or not args.url:
        _launch_tui()
        return

    config = load_config()
    headers = {key: value for key, value in config["headers"].items() if value}
    headers.update(parse_headers(args.header))
    keywords = args.keyword or config["filter_keywords"]
    threads = args.threads or int(config["threads"])
    output_path = args.output or _default_output_for_url(args.url)
    output = expand_path(output_path)

    media_info = detect_media_type(args.url, headers)
    print(f"detected {media_info.display_name}")
    if media_info.kind != MediaKind.HLS:
        if args.dump_filtered:
            raise SystemExit("--dump-filtered is only supported for HLS/m3u8 playlists")
        try:
            require_ffmpeg()
            print("downloading with ffmpeg")
            download_with_ffmpeg(args.url, output, headers)
        except Exception as exc:  # noqa: BLE001 - CLI should return a user-readable error.
            raise SystemExit(f"download failed: {exc}") from exc
        print(f"saved {output}")
        return

    try:
        playlist = _load_media_playlist(args.url, headers, args.variant)
    except Exception as exc:  # noqa: BLE001 - CLI must surface a concise failure.
        raise SystemExit(f"failed to load playlist: {exc}") from exc

    filtered = filter_playlist(playlist, keywords, args.regex)
    if not filtered.segments:
        raise SystemExit("no playable segments after filtering")
    if args.dump_filtered:
        expand_path(args.dump_filtered).write_text(playlist_to_m3u8(filtered), encoding="utf-8")

    uses_default_work_dir = not args.work_dir
    work_dir = expand_path(args.work_dir) if args.work_dir else Path(output_path).with_suffix("").resolve()

    try:
        require_ffmpeg()
        print(f"downloading {len(filtered.segments)} segments with {threads} workers")
        ts_files = Downloader(threads=threads, headers=headers).download(filtered.segments, work_dir, _print_progress)
        print("merging segments")
        merge_to_mp4(ts_files, output)
    except Exception as exc:  # noqa: BLE001 - CLI should return a user-readable error.
        raise SystemExit(f"download failed: {exc}") from exc
    finally:
        if uses_default_work_dir and not args.keep_segments and work_dir.exists():
            shutil.rmtree(work_dir)

    print(f"saved {output}")


def _launch_tui() -> None:
    try:
        from .tui.app import main as tui_main
    except ImportError as exc:
        raise SystemExit(
            "TUI dependencies are not installed; install requirements-desktop.txt or pass a URL to run CLI download."
        ) from exc
    tui_main()


def _load_media_playlist(url: str, headers: dict[str, str], variant_index: int = -1) -> Playlist:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    playlist = parse_playlist(response.text, url)
    if not playlist.is_master:
        return playlist

    if variant_index >= 0:
        try:
            variant = playlist.variants[variant_index]
        except IndexError as exc:
            raise ValueError(f"variant index out of range: {variant_index}") from exc
    else:
        variant = playlist.best_variant()
    if variant is None:
        raise ValueError("master playlist has no variants")
    response = requests.get(variant.url, headers=headers, timeout=30)
    response.raise_for_status()
    return parse_playlist(response.text, variant.url)


def _print_progress(done: int, total: int) -> None:
    percent = int(done / total * 100) if total else 100
    print(f"\rsegments: {done}/{total} ({percent}%)", end="\n" if done == total else "", file=sys.stderr)


def _default_output_for_url(url: str) -> str:
    extension = Path(urlparse(url).path).suffix.lower().lstrip(".")
    if not extension or extension in {"m3u", "m3u8", "mpd"} or len(extension) > 5:
        extension = "mp4"
    return f"video.{extension}"


if __name__ == "__main__":
    main()
