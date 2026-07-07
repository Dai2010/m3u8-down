from __future__ import annotations

import shutil
import asyncio
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config.manager import load_config
from ..core.downloader import Downloader
from ..core.filter import filter_playlist
from ..core.merger import merge_to_mp4
from ..core.proxy_server import ProxyServer
from ..core.utils import expand_path, require_ffmpeg
from ..main import _load_media_playlist
from .settings_dialog import SettingsDialog


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    failed = pyqtSignal(str)
    completed = pyqtSignal(str)

    def __init__(self, url: str, output: Path, config: dict, parent=None):
        super().__init__(parent)
        self.url = url
        self.output = output
        self.config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        work_dir = self.output.with_suffix("")
        try:
            headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
            keywords = self.config.get("filter_keywords", [])
            threads = int(self.config.get("threads", 16))

            require_ffmpeg()
            self.log.emit("Loading playlist")
            playlist = _load_media_playlist(self.url, headers)
            filtered = filter_playlist(playlist, keywords)
            if not filtered.segments:
                raise RuntimeError("no playable segments after filtering")

            self.log.emit(f"Downloading {len(filtered.segments)} segments")
            downloader = Downloader(threads=threads, headers=headers)
            ts_files = downloader.download(filtered.segments, work_dir, self.progress.emit, lambda: self._cancelled)
            if self._cancelled:
                raise RuntimeError("download cancelled")

            self.log.emit("Merging segments")
            merge_to_mp4(ts_files, self.output)
            self.completed.emit(str(self.output))
        except Exception as exc:  # noqa: BLE001 - show concise GUI error.
            self.failed.emit(str(exc))
        finally:
            if work_dir.exists() and not self._cancelled:
                shutil.rmtree(work_dir)


class ProxyWorker(QThread):
    started_url = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, url: str, config: dict, parent=None):
        super().__init__(parent)
        self.url = url
        self.config = config
        self.server: ProxyServer | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop_event: asyncio.Event | None = None

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run())

    def stop(self) -> None:
        if self.loop and self.stop_event:
            self.loop.call_soon_threadsafe(self.stop_event.set)

    async def _run(self) -> None:
        try:
            headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
            self.server = ProxyServer(
                port=int(self.config.get("proxy_port", 8888)),
                headers=headers,
                filter_keywords=self.config.get("filter_keywords", []),
            )
            await self.server.start()
            self.started_url.emit(self.server.get_stream_url(self.url))
            self.stop_event = asyncio.Event()
            await self.stop_event.wait()
        except Exception as exc:  # noqa: BLE001 - show concise GUI error.
            self.failed.emit(str(exc))
        finally:
            if self.server:
                await self.server.stop()
            if self.loop:
                self.loop.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("m3u8 Downloader")
        self.resize(820, 560)
        self.config = load_config()
        self.worker: DownloadWorker | None = None
        self.proxy_worker: ProxyWorker | None = None

        self.url = QLineEdit()
        self.url.setPlaceholderText("https://example.com/video/index.m3u8")

        self.output = QLineEdit(str(expand_path(self.config.get("save_dir", "~/Downloads")) / "video.mp4"))
        output_browse = QPushButton("Browse")
        output_browse.setObjectName("secondary")
        output_browse.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output)
        output_row.addWidget(output_browse)

        self.referer = QLineEdit(self.config.get("headers", {}).get("Referer", ""))

        form = QFormLayout()
        form.addRow("URL", self.url)
        form.addRow("Output", output_row)
        form.addRow("Referer", self.referer)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start_download)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("secondary")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_download)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("secondary")
        self.settings_button.clicked.connect(self._open_settings)
        self.proxy_button = QPushButton("Start Proxy")
        self.proxy_button.clicked.connect(self._start_proxy)
        self.stop_proxy_button = QPushButton("Stop Proxy")
        self.stop_proxy_button.setObjectName("secondary")
        self.stop_proxy_button.setEnabled(False)
        self.stop_proxy_button.clicked.connect(self._stop_proxy)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.settings_button)
        controls.addWidget(self.proxy_button)
        controls.addWidget(self.stop_proxy_button)
        controls.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QLabel("Idle")
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(controls)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _start_download(self) -> None:
        url = self.url.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter an m3u8 URL.")
            return
        output = expand_path(self.output.text().strip())
        headers = self.config.setdefault("headers", {})
        headers["Referer"] = self.referer.text().strip()

        self._set_running(True)
        self.progress.setValue(0)
        self.log.clear()
        self._append_log("Starting download")

        self.worker = DownloadWorker(url, output, self.config, self)
        self.worker.progress.connect(self._update_progress)
        self.worker.log.connect(self._append_log)
        self.worker.failed.connect(self._download_failed)
        self.worker.completed.connect(self._download_completed)
        self.worker.start()

    def _stop_download(self) -> None:
        if self.worker:
            self.worker.cancel()
            self._append_log("Stopping after current network operation")
            self.stop_button.setEnabled(False)

    def _start_proxy(self) -> None:
        url = self.url.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter an m3u8 URL.")
            return
        headers = self.config.setdefault("headers", {})
        headers["Referer"] = self.referer.text().strip()
        self.proxy_button.setEnabled(False)
        self.stop_proxy_button.setEnabled(True)
        self.proxy_worker = ProxyWorker(url, self.config, self)
        self.proxy_worker.started_url.connect(self._proxy_started)
        self.proxy_worker.failed.connect(self._proxy_failed)
        self.proxy_worker.start()

    def _stop_proxy(self) -> None:
        if self.proxy_worker:
            self.proxy_worker.stop()
            self.proxy_worker = None
        self.proxy_button.setEnabled(True)
        self.stop_proxy_button.setEnabled(False)
        self._append_log("Proxy stopped")

    def _proxy_started(self, proxy_url: str) -> None:
        self._append_log(f"Proxy URL: {proxy_url}")
        self.status.setText("Proxy running")

    def _proxy_failed(self, message: str) -> None:
        self._append_log(f"Proxy failed: {message}")
        self.proxy_button.setEnabled(True)
        self.stop_proxy_button.setEnabled(False)
        QMessageBox.critical(self, "Proxy failed", message)

    def _update_progress(self, done: int, total: int) -> None:
        value = int(done / total * 100) if total else 100
        self.progress.setValue(value)
        self.status.setText(f"Segments {done}/{total}")

    def _download_completed(self, output: str) -> None:
        self._append_log(f"Saved {output}")
        self.status.setText("Completed")
        self._set_running(False)

    def _download_failed(self, message: str) -> None:
        self._append_log(f"Failed: {message}")
        self.status.setText("Failed")
        self._set_running(False)
        QMessageBox.critical(self, "Download failed", message)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.config = load_config()
            self.referer.setText(self.config.get("headers", {}).get("Referer", ""))
            self._append_log("Settings saved")

    def _choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Choose output file", self.output.text(), "MP4 Video (*.mp4);;All Files (*)")
        if path:
            self.output.setText(path)

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.settings_button.setEnabled(not running)

    def _append_log(self, message: str) -> None:
        self.log.append(message)
