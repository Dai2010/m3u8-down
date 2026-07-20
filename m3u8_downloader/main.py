from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

from .config.manager import load_config
from .core.bilibili import (
    BilibiliProvider,
    BilibiliRequestConfig,
    BilibiliRequestError,
    BilibiliRequestSession,
    BilibiliSelectionPolicy,
    build_bilibili_headers,
    is_bilibili_url,
    parse_bilibili_input,
    prepare_bilibili_request,
)
from .core.bilibili_download import BilibiliDownloadOptions, download_bilibili_manifest
from .core.direct_downloader import download_direct_media
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
    parser.add_argument("--cookie", default="", help="B 站 Cookie，优先于配置文件中的 bilibili_cookie")
    parser.add_argument("--page", type=int, default=None, help="B 站分 P 编号，从 1 开始")
    parser.add_argument("--all-pages", action="store_true", help="下载 B 站视频的全部分 P")
    parser.add_argument("--quality", type=int, default=None, help="B 站最高画质 ID，例如 80")
    parser.add_argument("--video-codec", action="append", default=[], choices=["avc", "hevc", "av1"], help="B 站视频编码优先级，可重复指定")
    parser.add_argument("--audio-language", default="", help="B 站音频语言代码")
    parser.add_argument("--hdr", action="store_true", help="优先选择 HDR 视频轨道")
    parser.add_argument("--no-subtitles", action="store_true", help="不下载或封装 B 站字幕")
    parser.add_argument("--no-cover", action="store_true", help="不保存 B 站封面")
    parser.add_argument("--save-danmaku", action="store_true", help="保存 B 站弹幕 XML")
    parser.add_argument("--no-chapters", action="store_true", help="不写入 B 站章节")
    parser.add_argument("--no-info", action="store_true", help="不保存 B 站信息 JSON")
    parser.add_argument("--keep-bilibili-tracks", action="store_true", help="保留下载的视频/音频临时轨道")
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
    headers = build_bilibili_headers(config, url=args.url)
    headers.update(parse_headers(args.header))
    if args.cookie and is_bilibili_url(args.url):
        headers["Cookie"] = args.cookie
    keywords = args.keyword or config["filter_keywords"]
    threads = args.threads or int(config["threads"])
    output_path = args.output or _default_output_for_url(args.url)
    output = expand_path(output_path)
    bilibili_compat = bool(config.get("bilibili_compat", False)) or is_bilibili_url(args.url)
    request_url, request_headers = prepare_bilibili_request(args.url, headers, bilibili_compat)

    if is_bilibili_url(args.url) and parse_bilibili_input(args.url).kind in {"video", "short", "episode", "season", "course", "collection", "series"}:
        _download_bilibili_from_cli(args, config, headers)
        return

    media_info = detect_media_type(args.url, headers, bilibili_compat=bilibili_compat)
    print(f"detected {media_info.display_name}")
    if media_info.kind == MediaKind.PROGRESSIVE:
        try:
            print("downloading direct media")
            download_direct_media(args.url, output, headers, bilibili_compat=bilibili_compat)
        except Exception as exc:  # noqa: BLE001 - CLI should return a user-readable error.
            raise SystemExit(f"download failed: {exc}") from exc
        print(f"saved {output}")
        return

    if media_info.kind != MediaKind.HLS:
        if args.dump_filtered:
            raise SystemExit("--dump-filtered is only supported for HLS/m3u8 playlists")
        try:
            require_ffmpeg()
            print("downloading with ffmpeg")
            download_with_ffmpeg(request_url, output, request_headers, bilibili_compat=bilibili_compat)
        except Exception as exc:  # noqa: BLE001 - CLI should return a user-readable error.
            raise SystemExit(f"download failed: {exc}") from exc
        print(f"saved {output}")
        return

    try:
        playlist = _load_media_playlist(args.url, headers, args.variant, bilibili_compat=bilibili_compat)
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
        ts_files = Downloader(threads=threads, headers=request_headers, bilibili_compat=bilibili_compat).download(
            filtered.segments, work_dir, _print_progress
        )
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


def _download_bilibili_from_cli(args, config: dict, headers: dict[str, str]) -> None:
    input_kind = parse_bilibili_input(args.url).kind
    if input_kind in {"episode", "season", "course"}:
        raise SystemExit("番剧/课程下载未启用，请输入普通 BV/av 视频页面")
    if input_kind in {"collection", "series"}:
        raise SystemExit("合集批量下载暂未启用，请逐个输入 BV/av 视频页面")
    session = BilibiliRequestSession(
        BilibiliRequestConfig(
            headers=headers,
            cookie=str(headers.get("Cookie", "")),
            retries=3,
        ),
    )
    provider = BilibiliProvider(session)
    try:
        collection = provider.describe(args.url)
        selected_pages = _select_bilibili_pages(collection.pages, args.page, args.all_pages)
        require_ffmpeg()
        codec_order = tuple(args.video_codec) or ("avc", "hevc", "av1")
        options = BilibiliDownloadOptions(
            selection=BilibiliSelectionPolicy(
                video_codecs=codec_order,
                maximum_quality_id=args.quality,
                audio_language=args.audio_language,
                prefer_hdr=args.hdr,
            ),
            threads=max(1, args.threads or int(config["threads"])),
            retries=3,
            save_subtitles=not args.no_subtitles,
            save_cover=not args.no_cover,
            save_danmaku=args.save_danmaku,
            save_chapters=not args.no_chapters,
            save_info=not args.no_info,
            keep_intermediates=args.keep_bilibili_tracks,
        )
        for page_index in selected_pages:
            page = collection.pages[page_index - 1]
            output = _bilibili_output_path(args.output, collection.title, page.page, len(selected_pages))
            print(f"正在下载 P{page.page}: {page.title or collection.title}")
            manifest = provider.resolve(args.url, page=page.page)
            download_bilibili_manifest(
                manifest,
                output,
                session,
                options,
                progress_callback=lambda done, total, message: print(f"{message} ({done}/{total})"),
            )
            print(f"saved {output}")
    except BilibiliRequestError as exc:
        hint = "请检查 Cookie、Referer 或登录状态" if exc.category == "auth" else "请稍后重试并保留完整页面链接"
        raise SystemExit(f"B 站请求失败：{exc}；{hint}") from exc
    except Exception as exc:  # noqa: BLE001 - CLI presents one actionable error.
        raise SystemExit(f"B 站下载失败：{exc}") from exc


def _select_bilibili_pages(pages, requested_page: int | None, all_pages: bool) -> list[int]:
    if requested_page is not None:
        if requested_page < 1 or requested_page > len(pages):
            raise ValueError(f"分 P 编号必须在 1 到 {len(pages)} 之间")
        return [requested_page]
    if all_pages or len(pages) == 1:
        return [page.page for page in pages]
    print("B 站页面包含多个分 P：")
    for page in pages:
        print(f"  {page.page}. {page.title or '未命名'}")
    if not sys.stdin.isatty():
        print("非交互终端默认选择 P1，可使用 --page 或 --all-pages 修改")
        return [pages[0].page]
    value = input("请选择分 P 编号（默认 1）：").strip()
    selected = int(value or "1")
    if selected < 1 or selected > len(pages):
        raise ValueError(f"分 P 编号必须在 1 到 {len(pages)} 之间")
    return [selected]


def _bilibili_output_path(output: str, title: str, page: int, page_count: int) -> Path:
    if output:
        target = expand_path(output)
        if page_count == 1 and target.suffix:
            return target
        target.mkdir(parents=True, exist_ok=True)
        return target / f"{_safe_bilibili_name(title)}-P{page:02d}.mp4"
    return Path(f"{_safe_bilibili_name(title)}-P{page:02d}.mp4")


def _safe_bilibili_name(value: str) -> str:
    cleaned = "".join(character if character not in '\\/:*?\"<>|' else "_" for character in value).strip(" .")
    return cleaned or "bilibili-video"


def _load_media_playlist(url: str, headers: dict[str, str], variant_index: int = -1, bilibili_compat: bool = False) -> Playlist:
    request_url, request_headers = prepare_bilibili_request(url, headers, bilibili_compat)
    response = requests.get(request_url, headers=request_headers, timeout=30)
    response.raise_for_status()
    playlist = parse_playlist(response.text, request_url)
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
    variant_url, variant_headers = prepare_bilibili_request(variant.url, headers, bilibili_compat)
    response = requests.get(variant_url, headers=variant_headers, timeout=30)
    response.raise_for_status()
    return parse_playlist(response.text, variant_url)


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
