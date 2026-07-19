from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from urllib.parse import urlparse

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, Log, ProgressBar, Static, TabPane, TabbedContent

from ..config.manager import delete_profile, load_config, load_profiles, new_profile, save_profiles, upsert_profile
from ..config.theme import should_use_dark_theme
from ..core.direct_downloader import download_direct_media
from ..core.downloader import Downloader
from ..core.ffmpeg_downloader import download_with_ffmpeg
from ..core.filter import filter_playlist
from ..core.media_type import MediaInfo, MediaKind, detect_media_type
from ..core.merger import merge_to_mp4
from ..core.proxy_server import ProxyServer
from ..core.utils import expand_path, require_ffmpeg
from ..main import _load_media_playlist


class M3U8DownloaderTUI(App):
    CSS = """
    Screen { padding: 0; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 0; }
    .page {
        width: 100%;
        height: 1fr;
        padding: 1;
        overflow-y: scroll;
        scrollbar-size-vertical: 1;
    }
    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    Input {
        width: 100%;
        margin-bottom: 1;
    }
    Button {
        width: 100%;
        min-width: 1;
        margin: 0 0 1 0;
    }
    .actions { width: 100%; height: auto; }
    #status { margin: 1 0; }
    #progress { margin-bottom: 1; }
    #log { width: 100%; height: 1fr; min-height: 8; border: solid $surface; }
    """
    BINDINGS = [("q", "quit", "Quit")]
    DETECTION_DELAY_SECONDS = 1.0

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.dark = should_use_dark_theme(self.config.get("theme", "system"))
        self.profiles = load_profiles(self.config)
        self.active_profile_index = 0
        self.proxy: ProxyServer | None = None
        self.detection_task: asyncio.Task | None = None
        self.detected_url = ""
        self.detected_media_info: MediaInfo | None = None

    def compose(self) -> ComposeResult:
        profile = self.profiles[self.active_profile_index]
        yield Header()
        with TabbedContent(initial="download-tab"):
            with TabPane("下载", id="download-tab"):
                with VerticalScroll(classes="page"):
                    yield Label("媒体下载与流播", classes="section-title")
                    yield Input(placeholder="Media URL", id="url")
                    yield Button("立即探测（回车也可）", id="detect")
                    yield Input(value="", placeholder="Output path; blank uses URL extension", id="output")
                    yield Input(value=self.config.get("headers", {}).get("Referer", ""), placeholder="Referer", id="referer")
                    yield Static("输入链接后自动探测", id="status")
                    yield ProgressBar(total=100, id="progress")
                    with Vertical(classes="actions"):
                        yield Button("Download", id="download", variant="primary")
                        yield Button("Start Proxy", id="proxy", variant="success")
                        yield Button("Stop Proxy", id="stop-proxy", variant="default")
                    yield Label("下载、探测和代理操作均可在本页完成。", classes="hint")
            with TabPane("配置", id="profiles-tab"):
                with VerticalScroll(classes="page"):
                    yield Label("Profiles", classes="section-title")
                    yield Label("修改配置后点击保存；配置编号从 1 开始。", classes="hint")
                    yield Input(value="1", placeholder="Profile number", id="profile-index")
                    yield Input(value=profile.get("name", "默认配置"), placeholder="Profile name", id="profile-name")
                    yield Input(value=", ".join(profile.get("tags", [])), placeholder="Tags, comma separated", id="profile-tags")
                    yield Input(value=profile.get("note", ""), placeholder="Note", id="profile-note")
                    yield Input(value="yes" if profile.get("ad_filter", False) else "no", placeholder="Ad filter yes/no", id="profile-ad-filter")
                    yield Input(value=" | ".join(profile.get("filter_keywords", [])), placeholder="Filter keywords, separated by |", id="profile-keywords")
                    yield Input(value=str(profile.get("threads", self.config.get("threads", 16))), placeholder="Threads", id="profile-threads")
                    yield Input(value=profile.get("save_dir", self.config.get("save_dir", "~/Downloads")), placeholder="Save directory", id="profile-save-dir")
                    with Vertical(classes="actions"):
                        yield Button("Load Profile", id="load-profile")
                        yield Button("New Profile", id="new-profile")
                        yield Button("Save Profile", id="save-profile", variant="success")
                        yield Button("Delete Profile", id="delete-profile", variant="error")
            with TabPane("日志", id="logs-tab"):
                with VerticalScroll(classes="page"):
                    yield Label("运行日志", classes="section-title")
                    yield Log(id="log")
        yield Footer()

    def on_mount(self) -> None:
        self._write_profiles()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            self.run_worker(self._download(), exclusive=True)
        elif event.button.id == "detect":
            self._start_detection()
        elif event.button.id == "proxy":
            await self._start_proxy()
        elif event.button.id == "stop-proxy":
            await self._stop_proxy()
        elif event.button.id == "load-profile":
            self._load_profile()
        elif event.button.id == "new-profile":
            self._new_profile()
        elif event.button.id == "save-profile":
            self._save_profile()
        elif event.button.id == "delete-profile":
            self._delete_profile()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url":
            self._start_detection()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "url":
            return
        if self.detection_task and not self.detection_task.done():
            self.detection_task.cancel()
        self.detected_url = ""
        self.detected_media_info = None
        url = event.value.strip()
        if not url:
            self.query_one("#status", Static).update("请输入媒体链接")
            return
        self.query_one("#status", Static).update("将在 1 秒后自动探测，也可立即点击探测")
        self.detection_task = asyncio.create_task(self._detect_after_delay(url))

    def _start_detection(self) -> None:
        if self.detection_task and not self.detection_task.done():
            self.detection_task.cancel()
        url = self.query_one("#url", Input).value.strip()
        self.detected_url = ""
        self.detected_media_info = None
        if not url:
            self.query_one("#status", Static).update("请输入媒体链接")
            return
        self.query_one("#status", Static).update("正在探测媒体类型")
        self.detection_task = asyncio.create_task(self._detect_after_delay(url, delay=0))

    async def _detect_after_delay(self, url: str, delay: float = DETECTION_DELAY_SECONDS) -> None:
        try:
            await asyncio.sleep(delay)
            self.query_one("#status", Static).update("正在探测媒体类型")
            media_info = await asyncio.to_thread(detect_media_type, url, self._headers())
            if self.query_one("#url", Input).value.strip() != url:
                return
            self.detected_url = url
            self.detected_media_info = media_info
            self.query_one("#status", Static).update(f"已识别：{media_info.display_name}")
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001 - TUI displays concise detection failures.
            self.query_one("#status", Static).update(f"探测失败：{exc}")

    async def _download(self) -> None:
        url = self.query_one("#url", Input).value.strip()
        if not url:
            self._write("Enter a media URL")
            return

        output_text = self.query_one("#output", Input).value.strip()
        output = expand_path(output_text) if output_text else self._default_output_for_url(url)
        work_dir: Path | None = None
        try:
            headers = self._headers()
            if url != self.detected_url or self.detected_media_info is None:
                self._write("请先完成媒体探测")
                return
            media_info = self.detected_media_info
            self._write(f"Detected {media_info.display_name}")
            if media_info.kind == MediaKind.PROGRESSIVE:
                self._write("Downloading direct media")
                await asyncio.to_thread(download_direct_media, url, output, headers)
                self._write(f"Saved {output}")
                return

            require_ffmpeg()
            if media_info.kind != MediaKind.HLS:
                self._write("Downloading with FFmpeg")
                await asyncio.to_thread(download_with_ffmpeg, url, output, headers)
                self._write(f"Saved {output}")
                return

            self._write("Loading playlist")
            playlist = await asyncio.to_thread(_load_media_playlist, url, headers)
            filtered = filter_playlist(playlist, self._filter_keywords())
            if not filtered.segments:
                raise RuntimeError("no playable segments after filtering")

            def progress(done: int, total: int) -> None:
                percent = int(done / total * 100) if total else 100
                self.call_from_thread(self.query_one("#progress", ProgressBar).update, progress=percent)
                self.call_from_thread(self.query_one("#status", Static).update, f"Segments {done}/{total}")

            self._write(f"Downloading {len(filtered.segments)} segments")
            downloader = Downloader(threads=self._threads(), headers=headers)
            work_dir = output.with_suffix("")
            ts_files = await asyncio.to_thread(downloader.download, filtered.segments, work_dir, progress)
            self._write("Merging segments")
            await asyncio.to_thread(merge_to_mp4, ts_files, output)
            self._write(f"Saved {output}")
        except Exception as exc:  # noqa: BLE001 - TUI displays concise failures.
            self._write(f"Failed: {exc}")
        finally:
            if work_dir and work_dir.exists():
                shutil.rmtree(work_dir)

    async def _start_proxy(self) -> None:
        url = self.query_one("#url", Input).value.strip()
        if not url:
            self._write("Enter a media URL")
            return
        if self.proxy:
            self._write(self.proxy.get_stream_url(url))
            return
        if url != self.detected_url or self.detected_media_info is None:
            self._write("请先完成媒体探测")
            return
        headers = self._headers()
        media_info = self.detected_media_info
        self._write(f"Detected {media_info.display_name}")
        if media_info.kind != MediaKind.HLS:
            self._write(f"Playback URL: {url}")
            return

        self.proxy = ProxyServer(
            port=int(self.config.get("proxy_port", 8888)),
            headers=headers,
            filter_keywords=self._filter_keywords(),
        )
        await self.proxy.start()
        self._write(f"Proxy URL: {self.proxy.get_stream_url(url)}")

    async def _stop_proxy(self) -> None:
        if self.proxy:
            await self.proxy.stop()
            self.proxy = None
            self._write("Proxy stopped")

    async def action_quit(self) -> None:
        await self._stop_proxy()
        self.exit()

    def _headers(self) -> dict[str, str]:
        headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
        referer = self.query_one("#referer", Input).value.strip()
        if referer:
            headers["Referer"] = referer
        return headers

    def _threads(self) -> int:
        profile = self.profiles[self.active_profile_index]
        return int(profile.get("threads", self.config.get("threads", 16)))

    def _filter_keywords(self) -> list[str]:
        profile = self.profiles[self.active_profile_index]
        return list(profile.get("filter_keywords", [])) if profile.get("ad_filter", False) else []

    def _default_output_for_url(self, url: str) -> Path:
        profile = self.profiles[self.active_profile_index]
        output_dir = expand_path(profile.get("save_dir", self.config.get("save_dir", "~/Downloads")))
        extension = Path(urlparse(url).path).suffix.lower().lstrip(".")
        if not extension or extension in {"m3u", "m3u8", "mpd"} or len(extension) > 5:
            extension = "mp4"
        return output_dir / f"video.{extension}"

    def _profile_index(self) -> int:
        value = self.query_one("#profile-index", Input).value.strip()
        index = int(value or "1") - 1
        return min(max(index, 0), len(self.profiles) - 1)

    def _form_profile(self) -> dict:
        try:
            threads = int(self.query_one("#profile-threads", Input).value.strip() or self.config.get("threads", 16))
        except ValueError:
            threads = int(self.config.get("threads", 16))
        return {
            "name": self.query_one("#profile-name", Input).value.strip() or "未命名配置",
            "tags": [tag.strip() for tag in self.query_one("#profile-tags", Input).value.split(",") if tag.strip()],
            "note": self.query_one("#profile-note", Input).value.strip(),
            "ad_filter": self.query_one("#profile-ad-filter", Input).value.strip().lower() in {"1", "true", "yes", "y", "on", "开启"},
            "filter_keywords": [item.strip() for item in self.query_one("#profile-keywords", Input).value.replace("\n", "|").split("|") if item.strip()],
            "threads": threads,
            "save_dir": self.query_one("#profile-save-dir", Input).value.strip() or "~/Downloads",
        }

    def _apply_profile_inputs(self, index: int) -> None:
        profile = self.profiles[index]
        self.active_profile_index = index
        self.query_one("#profile-index", Input).value = str(index + 1)
        self.query_one("#profile-name", Input).value = profile.get("name", "默认配置")
        self.query_one("#profile-tags", Input).value = ", ".join(profile.get("tags", []))
        self.query_one("#profile-note", Input).value = profile.get("note", "")
        self.query_one("#profile-ad-filter", Input).value = "yes" if profile.get("ad_filter", False) else "no"
        self.query_one("#profile-keywords", Input).value = " | ".join(profile.get("filter_keywords", []))
        self.query_one("#profile-threads", Input).value = str(profile.get("threads", self.config.get("threads", 16)))
        self.query_one("#profile-save-dir", Input).value = profile.get("save_dir", self.config.get("save_dir", "~/Downloads"))
        self.query_one("#output", Input).value = ""

    def _load_profile(self) -> None:
        try:
            index = self._profile_index()
        except ValueError:
            self._write("Profile number must be numeric")
            return
        self._apply_profile_inputs(index)
        self._write(f"Loaded profile {index + 1}: {self.profiles[index].get('name', '未命名配置')}")

    def _new_profile(self) -> None:
        profile = new_profile(f"配置 {len(self.profiles) + 1}")
        self.profiles.append(profile)
        self._save_profiles()
        self._apply_profile_inputs(len(self.profiles) - 1)
        self._write_profiles()

    def _save_profile(self) -> None:
        try:
            index = self._profile_index()
        except ValueError:
            self._write("Profile number must be numeric")
            return
        self.profiles = upsert_profile(self.profiles, index, self._form_profile())
        self._save_profiles()
        self._apply_profile_inputs(index)
        self._write_profiles()

    def _delete_profile(self) -> None:
        try:
            index = self._profile_index()
        except ValueError:
            self._write("Profile number must be numeric")
            return
        if len(self.profiles) <= 1:
            self._write("Keep at least one profile")
            return
        self.profiles = delete_profile(self.profiles, index)
        self._save_profiles()
        self._apply_profile_inputs(min(index, len(self.profiles) - 1))
        self._write_profiles()

    def _save_profiles(self) -> None:
        self.config = save_profiles(self.profiles, self.config)

    def _write_profiles(self) -> None:
        lines = [f"{index + 1}. {profile.get('name', '未命名配置')}" for index, profile in enumerate(self.profiles)]
        self._write("Profiles: " + "; ".join(lines))

    def _write(self, message: str) -> None:
        self.query_one("#log", Log).write_line(message)


def main() -> None:
    M3U8DownloaderTUI().run()


if __name__ == "__main__":
    main()
