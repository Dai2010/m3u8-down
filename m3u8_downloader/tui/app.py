from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Log, ProgressBar, Static

from ..config.manager import load_config
from ..core.downloader import Downloader
from ..core.filter import filter_playlist
from ..core.merger import merge_to_mp4
from ..core.proxy_server import ProxyServer
from ..core.utils import expand_path, require_ffmpeg
from ..main import _load_media_playlist


class M3U8DownloaderTUI(App):
    CSS = """
    Screen { padding: 1; }
    Input { margin-bottom: 1; }
    Button { margin-right: 1; }
    #log { height: 1fr; border: solid $surface; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.proxy: ProxyServer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Input(placeholder="m3u8 URL", id="url")
            yield Input(value=str(expand_path(self.config.get("save_dir", "~/Downloads")) / "video.mp4"), placeholder="Output MP4", id="output")
            yield Input(value=self.config.get("headers", {}).get("Referer", ""), placeholder="Referer", id="referer")
            with Horizontal():
                yield Button("Download", id="download", variant="primary")
                yield Button("Start Proxy", id="proxy", variant="success")
                yield Button("Stop Proxy", id="stop-proxy", variant="default")
            yield ProgressBar(total=100, id="progress")
            yield Static("Idle", id="status")
            yield Log(id="log")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            self.run_worker(self._download(), exclusive=True)
        elif event.button.id == "proxy":
            await self._start_proxy()
        elif event.button.id == "stop-proxy":
            await self._stop_proxy()

    async def _download(self) -> None:
        url = self.query_one("#url", Input).value.strip()
        output = expand_path(self.query_one("#output", Input).value.strip())
        if not url:
            self._write("Enter an m3u8 URL")
            return

        work_dir = output.with_suffix("")
        try:
            headers = self._headers()
            require_ffmpeg()
            self._write("Loading playlist")
            playlist = await asyncio.to_thread(_load_media_playlist, url, headers)
            filtered = filter_playlist(playlist, self.config.get("filter_keywords", []))
            if not filtered.segments:
                raise RuntimeError("no playable segments after filtering")

            def progress(done: int, total: int) -> None:
                percent = int(done / total * 100) if total else 100
                self.call_from_thread(self.query_one("#progress", ProgressBar).update, progress=percent)
                self.call_from_thread(self.query_one("#status", Static).update, f"Segments {done}/{total}")

            self._write(f"Downloading {len(filtered.segments)} segments")
            downloader = Downloader(threads=int(self.config.get("threads", 16)), headers=headers)
            ts_files = await asyncio.to_thread(downloader.download, filtered.segments, work_dir, progress)
            self._write("Merging segments")
            await asyncio.to_thread(merge_to_mp4, ts_files, output)
            self._write(f"Saved {output}")
        except Exception as exc:  # noqa: BLE001 - TUI displays concise failures.
            self._write(f"Failed: {exc}")
        finally:
            if work_dir.exists():
                shutil.rmtree(work_dir)

    async def _start_proxy(self) -> None:
        url = self.query_one("#url", Input).value.strip()
        if not url:
            self._write("Enter an m3u8 URL")
            return
        if self.proxy:
            self._write(self.proxy.get_stream_url(url))
            return
        self.proxy = ProxyServer(
            port=int(self.config.get("proxy_port", 8888)),
            headers=self._headers(),
            filter_keywords=self.config.get("filter_keywords", []),
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

    def _write(self, message: str) -> None:
        self.query_one("#log", Log).write_line(message)


def main() -> None:
    M3U8DownloaderTUI().run()


if __name__ == "__main__":
    main()
