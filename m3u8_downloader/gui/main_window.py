from __future__ import annotations

import shutil
import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config.manager import load_config, load_profiles
from ..core.bilibili import is_bilibili_url, prepare_bilibili_request
from ..core.direct_downloader import download_direct_media
from ..core.downloader import Downloader
from ..core.ffmpeg_downloader import download_with_ffmpeg
from ..core.filter import filter_playlist
from ..core.media_type import MediaInfo, MediaKind, detect_media_type
from ..core.merger import merge_to_mp4
from ..core.proxy_server import ProxyServer
from ..core.utils import expand_path, require_ffmpeg
from ..main import _load_media_playlist
from .settings_dialog import SettingsDialog
from .theme import apply_gui_theme


@dataclass
class DownloadTask:
    url: str
    output_name: str
    media_info: MediaInfo | None = None


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    failed = pyqtSignal(str)
    completed = pyqtSignal(str)

    def __init__(self, tasks: list[DownloadTask], output_dir: Path, config: dict, parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self.output_dir = output_dir
        self.config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        work_root = self.output_dir / ".m3u8-downloader-segments"
        try:
            headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
            keywords = self.config.get("filter_keywords", [])
            threads = int(self.config.get("threads", 16))
            manual_bilibili_compat = bool(self.config.get("bilibili_compat", False))

            for task_index, task in enumerate(self.tasks, start=1):
                if self._cancelled:
                    raise RuntimeError("download cancelled")
                output = self.output_dir / task.output_name
                work_dir = work_root / str(task_index)
                bilibili_compat = manual_bilibili_compat or is_bilibili_url(task.url)
                request_url, request_headers = prepare_bilibili_request(task.url, headers, bilibili_compat)
                self.log.emit(f"[{task_index}/{len(self.tasks)}] Detecting media type")
                media_info = task.media_info or detect_media_type(task.url, headers, bilibili_compat=bilibili_compat)
                self.log.emit(f"[{task_index}/{len(self.tasks)}] Detected {media_info.display_name}")
                if media_info.kind == MediaKind.PROGRESSIVE:
                    self.log.emit(f"[{task_index}/{len(self.tasks)}] Downloading direct media")
                    download_direct_media(task.url, output, headers, cancel_callback=lambda: self._cancelled, bilibili_compat=bilibili_compat)
                    self.log.emit(f"Saved {output}")
                    continue

                require_ffmpeg()
                if media_info.kind != MediaKind.HLS:
                    self.log.emit(f"[{task_index}/{len(self.tasks)}] Downloading with FFmpeg")
                    download_with_ffmpeg(request_url, output, request_headers, bilibili_compat=bilibili_compat)
                    self.log.emit(f"Saved {output}")
                    continue

                self.log.emit(f"[{task_index}/{len(self.tasks)}] Loading playlist")
                playlist = _load_media_playlist(request_url, request_headers, bilibili_compat=bilibili_compat)
                filtered = filter_playlist(playlist, keywords)
                if not filtered.segments:
                    raise RuntimeError("no playable segments after filtering")

                self.log.emit(f"[{task_index}/{len(self.tasks)}] Downloading {len(filtered.segments)} segments")
                downloader = Downloader(threads=threads, headers=request_headers, bilibili_compat=bilibili_compat)
                ts_files = downloader.download(filtered.segments, work_dir, self.progress.emit, lambda: self._cancelled)
                if self._cancelled:
                    raise RuntimeError("download cancelled")

                self.log.emit(f"[{task_index}/{len(self.tasks)}] Merging segments")
                output.parent.mkdir(parents=True, exist_ok=True)
                merge_to_mp4(ts_files, output)
                self.log.emit(f"Saved {output}")
            self.completed.emit(str(self.output_dir))
        except Exception as exc:  # noqa: BLE001 - show concise GUI error.
            self.failed.emit(str(exc))
        finally:
            if work_root.exists() and not self._cancelled:
                shutil.rmtree(work_root)


class ProxyWorker(QThread):
    started_url = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, url: str, config: dict, media_info: MediaInfo | None = None, parent=None):
        super().__init__(parent)
        self.url = url
        self.config = config
        self.media_info = media_info
        self.server: ProxyServer | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.stop_event: asyncio.Event | None = None

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run())
        finally:
            self.loop.close()

    def stop(self) -> None:
        if self.loop and self.stop_event:
            self.loop.call_soon_threadsafe(self.stop_event.set)

    async def _run(self) -> None:
        try:
            headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
            bilibili_compat = bool(self.config.get("bilibili_compat", False)) or is_bilibili_url(self.url)
            request_url, request_headers = prepare_bilibili_request(self.url, headers, bilibili_compat)
            media_info = self.media_info or detect_media_type(self.url, headers, bilibili_compat=bilibili_compat)
            if media_info.kind != MediaKind.HLS:
                self.started_url.emit(request_url, media_info.display_name)
                return

            self.server = ProxyServer(
                port=int(self.config.get("proxy_port", 8888)),
                headers=request_headers,
                filter_keywords=self.config.get("filter_keywords", []),
                bilibili_compat=bilibili_compat,
            )
            await self.server.start()
            self.started_url.emit(self.server.get_stream_url(request_url), media_info.display_name)
            self.stop_event = asyncio.Event()
            await self.stop_event.wait()
        except Exception as exc:  # noqa: BLE001 - show concise GUI error.
            self.failed.emit(str(exc))
        finally:
            if self.server:
                await self.server.stop()


class PlaylistPreviewWorker(QThread):
    loaded = pyqtSignal(str, str)
    failed = pyqtSignal(str)

    def __init__(self, url: str, headers: dict[str, str], bilibili_compat: bool = False, parent=None):
        super().__init__(parent)
        self.url = url
        self.headers = headers
        self.bilibili_compat = bilibili_compat

    def run(self) -> None:
        try:
            request_url, request_headers = prepare_bilibili_request(self.url, self.headers, self.bilibili_compat)
            response = requests.get(request_url, headers=request_headers, timeout=30)
            response.raise_for_status()
            self.loaded.emit(self.url, response.text)
        except Exception as exc:  # noqa: BLE001 - show concise GUI error.
            self.failed.emit(str(exc))


class MediaDetectionWorker(QThread):
    detected = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(self, url: str, headers: dict[str, str], bilibili_compat: bool = False, parent=None):
        super().__init__(parent)
        self.url = url
        self.headers = headers
        self.bilibili_compat = bilibili_compat

    def run(self) -> None:
        try:
            self.detected.emit(self.url, detect_media_type(self.url, self.headers, bilibili_compat=self.bilibili_compat))
        except Exception as exc:  # noqa: BLE001 - show concise detection error.
            self.failed.emit(self.url, str(exc))


class PlaylistPreviewDialog(QDialog):
    def __init__(self, url: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("m3u8 列表预览")
        self.resize(820, 600)
        layout = QVBoxLayout(self)
        title = QLabel("m3u8 列表全文")
        title.setObjectName("title")
        source = QLabel(url)
        source.setObjectName("subtitle")
        source.setWordWrap(True)
        reader = QPlainTextEdit(content)
        reader.setObjectName("playlistPreview")
        reader.setReadOnly(True)
        reader.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        reader.setFont(QFont("monospace", 10))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(title)
        layout.addWidget(source)
        layout.addWidget(reader, 1)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("m3u8 Downloader")
        self.resize(900, 620)
        self.config = load_config()
        self.profiles = load_profiles(self.config)
        self.active_profile = self.profiles[0]
        self.worker: DownloadWorker | None = None
        self.proxy_worker: ProxyWorker | None = None
        self.preview_worker: PlaylistPreviewWorker | None = None
        self.download_rows: list[tuple[QLineEdit, QLineEdit, QWidget]] = []
        self.media_info_cache: dict[str, MediaInfo] = {}
        self.detection_workers: set[MediaDetectionWorker] = set()
        self.stream_media_info: MediaInfo | None = None
        self.stream_detected_url = ""
        self.download_row_status: dict[QLineEdit, QLabel] = {}
        self.download_row_preview: dict[QLineEdit, QPushButton] = {}
        self.download_row_timers: dict[QLineEdit, QTimer] = {}

        self.stack = QStackedWidget()
        self.home_page = self._build_home_page()
        self.stream_page = self._build_stream_page()
        self.download_page = self._build_download_page()
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.stream_page)
        self.stack.addWidget(self.download_page)
        self.setCentralWidget(self.stack)

    def _start_download(self) -> None:
        if not self._choose_download_mode():
            return
        pending = [
            url_edit.text().strip()
            for url_edit, _, _ in self.download_rows
            if url_edit.text().strip() and (self.media_info_cache.get(url_edit.text().strip()) is None or self.media_info_cache[url_edit.text().strip()].kind == MediaKind.UNKNOWN)
        ]
        if pending:
            if any(self.media_info_cache.get(url).kind == MediaKind.UNKNOWN for url in pending if self.media_info_cache.get(url)):
                QMessageBox.warning(self, "Unknown media", "Some URLs could not be detected. Check the links or request headers.")
            else:
                QMessageBox.information(self, "Media detection pending", "Wait for the 5-second media detection to finish for every URL before downloading.")
            return
        tasks = self._download_tasks()
        if not tasks:
            QMessageBox.warning(self, "Missing URL", "Add at least one media URL.")
            return
        output_dir = expand_path(self.output.text().strip())
        config = self._runtime_config(
            self.download_referer.text().strip(),
            self.download_ad_filter.isChecked(),
            self.download_keywords.toPlainText(),
            self.download_threads.value(),
            self.download_bilibili_compat.isChecked(),
        )

        self._set_running(True)
        self.progress.setValue(0)
        self.log.clear()
        self._append_log(f"Starting {len(tasks)} download task(s)")

        self.worker = DownloadWorker(tasks, output_dir, config, self)
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
        url = self.stream_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter a media URL.")
            return
        if url != self.stream_detected_url or self.stream_media_info is None:
            QMessageBox.information(self, "Media detection pending", "Wait for the 5-second media detection to finish before starting playback.")
            return
        if self.stream_media_info.kind == MediaKind.UNKNOWN:
            QMessageBox.warning(self, "Unknown media", "The media type could not be detected. Check the URL or request headers.")
            return
        config = self._runtime_config(
            self.stream_referer.text().strip(),
            self.stream_ad_filter.isChecked(),
            self.stream_keywords.toPlainText(),
            bilibili_compat=self.stream_bilibili_compat.isChecked(),
        )
        self.proxy_button.setEnabled(False)
        self.stop_proxy_button.setEnabled(True)
        self.proxy_worker = ProxyWorker(url, config, self.stream_media_info, self)
        self.proxy_worker.started_url.connect(self._proxy_started)
        self.proxy_worker.failed.connect(self._proxy_failed)
        self.proxy_worker.finished.connect(self._proxy_finished)
        self.proxy_worker.start()

    def _preview_playlist(
        self,
        url: str,
        referer: str,
        media_info: MediaInfo | None = None,
        detected_url: str = "",
        bilibili_compat: bool = False,
    ) -> None:
        url = url.strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter an m3u8 URL before previewing.")
            return
        if url != detected_url or media_info is None:
            QMessageBox.information(self, "Media detection pending", "Wait for the 5-second media detection to finish before previewing.")
            return
        if media_info.kind != MediaKind.HLS:
            QMessageBox.warning(self, "Not an m3u8 playlist", f"Detected {media_info.display_name}; m3u8 preview is only available for HLS playlists.")
            return
        if self.preview_worker and self.preview_worker.isRunning():
            QMessageBox.information(self, "Preview running", "m3u8 preview is already loading.")
            return
        headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
        if referer.strip():
            headers["Referer"] = referer.strip()
        self._append_stream_log("Loading m3u8 preview")
        self.preview_worker = PlaylistPreviewWorker(url, headers, bilibili_compat, self)
        self.preview_worker.loaded.connect(self._playlist_preview_loaded)
        self.preview_worker.failed.connect(self._playlist_preview_failed)
        self.preview_worker.finished.connect(lambda: setattr(self, "preview_worker", None))
        self.preview_worker.start()

    def _start_media_detection(
        self,
        url: str,
        headers: dict[str, str],
        on_detected,
        on_failed,
        use_cache: bool = True,
        bilibili_compat: bool = False,
    ) -> None:
        if use_cache:
            cached = self.media_info_cache.get(url)
            if cached is not None:
                on_detected(url, cached)
                return
        worker = MediaDetectionWorker(url, headers, bilibili_compat, self)
        self.detection_workers.add(worker)
        worker.detected.connect(on_detected)
        worker.failed.connect(on_failed)
        worker.finished.connect(lambda: self.detection_workers.discard(worker))
        worker.start()

    def _schedule_stream_detection(self) -> None:
        if not hasattr(self, "stream_url"):
            return
        url = self.stream_url.text().strip()
        self.stream_media_info = None
        self.stream_detected_url = ""
        self.preview_button.setEnabled(False)
        self.proxy_button.setEnabled(False)
        if not url:
            self.stream_status.setText("输入链接后等待 5 秒自动探测")
            return
        self.stream_status.setText("将在 5 秒后探测媒体类型")
        self.stream_detect_timer.start(5000)

    def _detect_stream_url(self) -> None:
        url = self.stream_url.text().strip()
        if not url:
            return
        self.stream_status.setText("正在探测媒体类型")
        headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
        if self.stream_referer.text().strip():
            headers["Referer"] = self.stream_referer.text().strip()
        self._start_media_detection(
            url,
            headers,
            self._stream_detection_completed,
            self._stream_detection_failed,
            use_cache=False,
            bilibili_compat=self.stream_bilibili_compat.isChecked(),
        )

    def _stream_detection_completed(self, url: str, media_info: MediaInfo) -> None:
        if url != self.stream_url.text().strip():
            return
        self.stream_media_info = media_info
        self.stream_detected_url = url
        self.proxy_button.setEnabled(media_info.kind != MediaKind.UNKNOWN)
        self.preview_button.setEnabled(media_info.kind == MediaKind.HLS)
        self.stream_status.setText(f"已识别：{media_info.display_name}")

    def _stream_detection_failed(self, url: str, message: str) -> None:
        if url == self.stream_url.text().strip():
            self.stream_status.setText(f"探测失败：{message}")

    def _invalidate_media_detection(self) -> None:
        self.media_info_cache.clear()
        if hasattr(self, "stream_url"):
            self._schedule_stream_detection()
        for url_edit in self.download_row_timers:
            self._schedule_download_detection(url_edit)

    def _schedule_download_detection(self, url_edit: QLineEdit) -> None:
        url = url_edit.text().strip()
        status = self.download_row_status[url_edit]
        preview = self.download_row_preview[url_edit]
        preview.setEnabled(False)
        if not url:
            status.setText("等待输入链接")
            return
        cached = self.media_info_cache.get(url)
        if cached is not None:
            self._download_detection_completed(url_edit, url, cached)
            return
        status.setText("将在 5 秒后探测媒体类型")
        self.download_row_timers[url_edit].start(5000)

    def _detect_download_url(self, url_edit: QLineEdit) -> None:
        url = url_edit.text().strip()
        if not url:
            return
        self.download_row_status[url_edit].setText("正在探测媒体类型")
        headers = {key: value for key, value in self.config.get("headers", {}).items() if value}
        if self.download_referer.text().strip():
            headers["Referer"] = self.download_referer.text().strip()
        self._start_media_detection(
            url,
            headers,
            lambda detected_url, info: self._download_detection_completed(url_edit, detected_url, info),
            lambda detected_url, message: self._download_detection_failed(url_edit, detected_url, message),
            bilibili_compat=self.download_bilibili_compat.isChecked(),
        )

    def _download_detection_completed(self, url_edit: QLineEdit, url: str, media_info: MediaInfo) -> None:
        self.media_info_cache[url] = media_info
        status = self.download_row_status.get(url_edit)
        preview = self.download_row_preview.get(url_edit)
        if url != url_edit.text().strip() or status is None or preview is None:
            return
        status.setText(f"已识别：{media_info.display_name}")
        preview.setEnabled(media_info.kind == MediaKind.HLS)

    def _download_detection_failed(self, url_edit: QLineEdit, url: str, message: str) -> None:
        status = self.download_row_status.get(url_edit)
        if url == url_edit.text().strip() and status is not None:
            status.setText(f"探测失败：{message}")

    def _stop_proxy(self) -> None:
        if self.proxy_worker:
            self.proxy_worker.stop()
            self.proxy_worker = None
        self.proxy_button.setEnabled(True)
        self.stop_proxy_button.setEnabled(False)
        self._append_stream_log("Proxy stopped")

    def _proxy_started(self, proxy_url: str, media_name: str) -> None:
        self._append_stream_log(f"Detected {media_name}")
        self._append_stream_log(f"Playback URL: {proxy_url}")
        self.stream_status.setText("Proxy running" if self.proxy_worker and self.proxy_worker.server else "Direct media URL")

    def _proxy_failed(self, message: str) -> None:
        self._append_stream_log(f"Proxy failed: {message}")
        self.proxy_button.setEnabled(True)
        self.stop_proxy_button.setEnabled(False)
        QMessageBox.critical(self, "Proxy failed", message)

    def _proxy_finished(self) -> None:
        if self.proxy_worker and self.proxy_worker.server:
            return
        self.proxy_button.setEnabled(True)
        self.stop_proxy_button.setEnabled(False)

    def _playlist_preview_loaded(self, url: str, content: str) -> None:
        PlaylistPreviewDialog(url, content, self).exec()

    def _playlist_preview_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Preview failed", message)

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
        dialog = SettingsDialog(self.config, self.profiles, self)
        if dialog.exec():
            self.config = load_config()
            self.profiles = load_profiles(self.config)
            self.active_profile = self.profiles[0]
            app = QApplication.instance()
            if app is not None:
                apply_gui_theme(app, self.config.get("theme", "system"), self.config.get("button_color", ""))
            referer = self.config.get("headers", {}).get("Referer", "")
            self.stream_referer.setText(referer)
            self.download_referer.setText(referer)
            bilibili_compat = bool(self.config.get("bilibili_compat", False))
            self.stream_bilibili_compat.setChecked(bilibili_compat)
            self.download_bilibili_compat.setChecked(bilibili_compat)
            self.download_threads.setValue(int(self.config.get("threads", 16)))
            self._apply_profile(self.active_profile)
            self._invalidate_media_detection()
            self._append_log("Settings saved")

    def _choose_download_mode(self) -> bool:
        dialog = DownloadModeDialog(self.profiles, self)
        if not dialog.exec():
            return False
        if dialog.selected_profile is not None:
            self.active_profile = dialog.selected_profile
            self._apply_profile(self.active_profile)
        return True

    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose output directory", self.output.text())
        if path:
            self.output.setText(path)

    def _add_download_row(self, url: str = "", output_name: str = "") -> None:
        row_widget = QWidget()
        layout = QVBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        url_row = QHBoxLayout()
        url_edit = QLineEdit(url)
        url_edit.setPlaceholderText("https://example.com/video/index.m3u8 or video.mp4")
        preview = QPushButton("预览 m3u8")
        preview.setObjectName("secondary")
        remove = QPushButton("删除")
        remove.setObjectName("secondary")
        url_row.addWidget(url_edit)
        url_row.addWidget(preview)
        url_row.addWidget(remove)
        output_edit = QLineEdit(output_name)
        output_edit.setPlaceholderText("留空则按 URL 自动命名")
        output_edit.setStyleSheet("margin-left: 28px;")
        layout.addLayout(url_row)
        layout.addWidget(output_edit)
        self.download_rows_layout.addWidget(row_widget)
        self.download_rows.append((url_edit, output_edit, row_widget))
        preview.clicked.connect(
            lambda: self._preview_playlist(
                url_edit.text(),
                self.download_referer.text(),
                self.media_info_cache.get(url_edit.text().strip()),
                url_edit.text().strip(),
                self.download_bilibili_compat.isChecked(),
            )
        )
        remove.clicked.connect(lambda: self._remove_download_row(row_widget))
        status = QLabel("等待输入链接")
        layout.addWidget(status)
        timer = QTimer(url_edit)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._detect_download_url(url_edit))
        self.download_row_status[url_edit] = status
        self.download_row_preview[url_edit] = preview
        self.download_row_timers[url_edit] = timer
        url_edit.textChanged.connect(lambda _text: self._schedule_download_detection(url_edit))
        self._schedule_download_detection(url_edit)

    def _remove_download_row(self, row_widget: QWidget) -> None:
        removed = [row for row in self.download_rows if row[2] is row_widget]
        self.download_rows = [row for row in self.download_rows if row[2] is not row_widget]
        for url_edit, _, _ in removed:
            self.download_row_status.pop(url_edit, None)
            self.download_row_preview.pop(url_edit, None)
            timer = self.download_row_timers.pop(url_edit, None)
            if timer:
                timer.stop()
        row_widget.setParent(None)
        row_widget.deleteLater()

    def _download_tasks(self) -> list[DownloadTask]:
        tasks: list[DownloadTask] = []
        for index, (url_edit, output_edit, _) in enumerate(self.download_rows, start=1):
            url = url_edit.text().strip()
            if not url:
                continue
            output_name = output_edit.text().strip()
            if not output_name or output_name in {"video.mp4", f"video-{index:03d}.mp4"}:
                output_name = _output_name_for_url(url, index, output_name)
            media_info = self.media_info_cache.get(url)
            if media_info is None or media_info.kind == MediaKind.UNKNOWN:
                continue
            tasks.append(DownloadTask(url, output_name, media_info))
        return tasks

    def _apply_profile(self, profile: dict) -> None:
        self.download_ad_filter.setChecked(bool(profile.get("ad_filter", False)))
        self.download_keywords.setPlainText("\n".join(profile.get("filter_keywords", [])))
        self.download_threads.setValue(int(profile.get("threads", 16)))
        self.output.setText(str(expand_path(profile.get("save_dir", "~/Downloads"))))
        self._sync_filter_visibility()

    def _set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.settings_button.setEnabled(not running)
        if hasattr(self, "preview_button"):
            self.preview_button.setEnabled(not running and self.stream_media_info is not None and self.stream_media_info.kind == MediaKind.HLS)
        for url_edit, preview in self.download_row_preview.items():
            url = url_edit.text().strip()
            media_info = self.media_info_cache.get(url)
            preview.setEnabled(not running and media_info is not None and media_info.kind == MediaKind.HLS)

    def _append_log(self, message: str) -> None:
        self.log.append(message)

    def _append_stream_log(self, message: str) -> None:
        self.stream_log.append(message)

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        title = QLabel("m3u8 Downloader")
        title.setObjectName("title")
        subtitle = QLabel("选择要做的事情")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stream = QPushButton("流播\n在线播放")
        stream.setObjectName("entry")
        stream.clicked.connect(lambda: self.stack.setCurrentWidget(self.stream_page))
        download = QPushButton("下载\n保存视频")
        download.setObjectName("entry")
        download.clicked.connect(lambda: self.stack.setCurrentWidget(self.download_page))
        settings = QPushButton("设置\n配置、主题、关于")
        settings.setObjectName("entry")
        settings.clicked.connect(self._open_settings)
        layout.addWidget(stream)
        layout.addWidget(download)
        layout.addWidget(settings)
        layout.addStretch(1)
        return page

    def _build_stream_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addLayout(self._header_row("流播"))

        self.stream_url = QLineEdit()
        self.stream_url.setPlaceholderText("https://example.com/video/index.m3u8 or video.mp4")
        self.stream_referer = QLineEdit(self.config.get("headers", {}).get("Referer", ""))
        self.stream_detect_timer = QTimer(self)
        self.stream_detect_timer.setSingleShot(True)
        self.stream_detect_timer.timeout.connect(self._detect_stream_url)
        self.stream_ad_filter = QCheckBox("启用去广告过滤")
        self.stream_ad_filter.toggled.connect(self._sync_filter_visibility)
        self.stream_bilibili_compat = QCheckBox("开启B站兼容模式")
        self.stream_bilibili_compat.setChecked(bool(self.config.get("bilibili_compat", False)))
        self.stream_bilibili_compat.toggled.connect(lambda _checked: self._schedule_stream_detection())
        self.stream_keywords = QTextEdit("\n".join(self.config.get("filter_keywords", [])))
        self.stream_keywords.setFixedHeight(96)
        self.stream_keywords_label = QLabel("过滤关键词，每行一个")

        form = QFormLayout()
        form.addRow("媒体地址", self.stream_url)
        layout.addLayout(form)
        advanced_toggle = QPushButton("高级")
        advanced_toggle.setCheckable(True)
        advanced_toggle.setChecked(False)
        advanced_panel = QWidget()
        advanced_form = QFormLayout(advanced_panel)
        advanced_form.addRow("Referer，可留空", self.stream_referer)
        advanced_form.addRow("", self.stream_bilibili_compat)
        advanced_form.addRow("", self.stream_ad_filter)
        advanced_form.addRow(self.stream_keywords_label, self.stream_keywords)
        advanced_panel.setVisible(False)
        advanced_toggle.toggled.connect(advanced_panel.setVisible)
        layout.addWidget(advanced_toggle)
        layout.addWidget(advanced_panel)

        self.proxy_button = QPushButton("开始流播")
        self.proxy_button.clicked.connect(self._start_proxy)
        self.preview_button = QPushButton("预览 m3u8 列表")
        self.preview_button.setObjectName("secondary")
        self.preview_button.clicked.connect(
            lambda: self._preview_playlist(
                self.stream_url.text(),
                self.stream_referer.text(),
                self.stream_media_info,
                self.stream_detected_url,
                self.stream_bilibili_compat.isChecked(),
            )
        )
        self.stop_proxy_button = QPushButton("停止流播")
        self.stop_proxy_button.setObjectName("secondary")
        self.stop_proxy_button.setEnabled(False)
        self.stop_proxy_button.clicked.connect(self._stop_proxy)
        controls = QHBoxLayout()
        controls.addWidget(self.proxy_button)
        controls.addWidget(self.preview_button)
        controls.addWidget(self.stop_proxy_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.stream_status = QLabel("等待操作")
        self.stream_log = QTextEdit()
        self.stream_log.setReadOnly(True)
        layout.addWidget(self.stream_status)
        layout.addWidget(self.stream_log, 1)
        self.stream_url.textChanged.connect(lambda _text: self._schedule_stream_detection())
        self.stream_referer.textChanged.connect(lambda _text: self._schedule_stream_detection())
        self._schedule_stream_detection()
        return page

    def _build_download_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addLayout(self._header_row("下载"))

        self.download_referer = QLineEdit(self.config.get("headers", {}).get("Referer", ""))
        self.download_referer.textChanged.connect(lambda _text: self._invalidate_media_detection())
        self.output = QLineEdit(str(expand_path(self.active_profile.get("save_dir", self.config.get("save_dir", "~/Downloads")))))
        output_browse = QPushButton("选择")
        output_browse.setObjectName("secondary")
        output_browse.clicked.connect(self._choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output)
        output_row.addWidget(output_browse)
        self.download_threads = QSpinBox()
        self.download_threads.setRange(1, 128)
        self.download_threads.setValue(int(self.active_profile.get("threads", self.config.get("threads", 16))))
        self.download_ad_filter = QCheckBox("启用去广告过滤")
        self.download_ad_filter.setChecked(bool(self.active_profile.get("ad_filter", False)))
        self.download_ad_filter.toggled.connect(self._sync_filter_visibility)
        self.download_bilibili_compat = QCheckBox("开启B站兼容模式")
        self.download_bilibili_compat.setChecked(bool(self.config.get("bilibili_compat", False)))
        self.download_bilibili_compat.toggled.connect(lambda _checked: self._invalidate_media_detection())
        self.download_keywords = QTextEdit("\n".join(self.active_profile.get("filter_keywords", self.config.get("filter_keywords", []))))
        self.download_keywords.setFixedHeight(96)
        self.download_keywords_label = QLabel("过滤关键词，每行一个")
        self.download_rows_layout = QVBoxLayout()
        add_url = QPushButton("添加 URL")
        add_url.setObjectName("secondary")
        add_url.clicked.connect(lambda: self._add_download_row())

        form = QFormLayout()
        form.addRow("保存目录", output_row)
        form.addRow("并发线程数", self.download_threads)
        layout.addLayout(form)
        advanced_toggle = QPushButton("高级")
        advanced_toggle.setCheckable(True)
        advanced_toggle.setChecked(False)
        advanced_panel = QWidget()
        advanced_form = QFormLayout(advanced_panel)
        advanced_form.addRow("Referer，可留空", self.download_referer)
        advanced_form.addRow("", self.download_bilibili_compat)
        advanced_form.addRow("", self.download_ad_filter)
        advanced_form.addRow(self.download_keywords_label, self.download_keywords)
        advanced_panel.setVisible(False)
        advanced_toggle.toggled.connect(advanced_panel.setVisible)
        layout.addWidget(advanced_toggle)
        layout.addWidget(advanced_panel)
        layout.addWidget(QLabel("下载任务"))
        layout.addLayout(self.download_rows_layout)
        layout.addWidget(add_url)
        self._add_download_row()

        self.start_button = QPushButton("开始下载")
        self.start_button.clicked.connect(self._start_download)
        self.stop_button = QPushButton("停止下载")
        self.stop_button.setObjectName("secondary")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_download)
        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("secondary")
        self.settings_button.clicked.connect(self._open_settings)
        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.settings_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.status = QLabel("等待操作")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)
        self._sync_filter_visibility()
        return page

    def _header_row(self, title: str) -> QHBoxLayout:
        row = QHBoxLayout()
        back = QPushButton("返回")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self.stack.setCurrentWidget(self.home_page))
        label = QLabel(title)
        label.setObjectName("title")
        row.addWidget(back)
        row.addWidget(label)
        row.addStretch(1)
        return row

    def _sync_filter_visibility(self) -> None:
        stream_visible = getattr(self, "stream_ad_filter", None) and self.stream_ad_filter.isChecked()
        download_visible = getattr(self, "download_ad_filter", None) and self.download_ad_filter.isChecked()
        if hasattr(self, "stream_keywords"):
            self.stream_keywords.setVisible(bool(stream_visible))
            self.stream_keywords_label.setVisible(bool(stream_visible))
        if hasattr(self, "download_keywords"):
            self.download_keywords.setVisible(bool(download_visible))
            self.download_keywords_label.setVisible(bool(download_visible))

    def _runtime_config(
        self,
        referer: str,
        ad_filter: bool,
        keywords_text: str,
        threads: int | None = None,
        bilibili_compat: bool = False,
    ) -> dict:
        config = self.config.copy()
        headers = config.get("headers", {}).copy()
        headers["Referer"] = referer
        config["headers"] = headers
        config["filter_keywords"] = [line.strip() for line in keywords_text.splitlines() if line.strip()] if ad_filter else []
        if threads is not None:
            config["threads"] = threads
        config["bilibili_compat"] = bilibili_compat
        return config

class DownloadModeDialog(QDialog):
    def __init__(self, profiles: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("下载方式")
        self.selected_profile: dict | None = profiles[0] if profiles else None
        layout = QVBoxLayout(self)
        self.use_profile = QRadioButton("使用已有配置")
        self.use_profile.setChecked(bool(profiles))
        self.guided = QRadioButton("引导式下载")
        self.combo = QComboBox()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.profiles = profiles
        for profile in profiles:
            self.combo.addItem(profile_label(profile))
        self.combo.currentIndexChanged.connect(self._profile_changed)
        layout.addWidget(self.use_profile)
        layout.addWidget(self.combo)
        layout.addWidget(self.summary)
        layout.addWidget(self.guided)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._profile_changed(0)

    def accept(self) -> None:
        self.selected_profile = self.profiles[self.combo.currentIndex()] if self.use_profile.isChecked() and self.profiles else None
        super().accept()

    def _profile_changed(self, index: int) -> None:
        if not self.profiles:
            self.summary.setText("没有已有配置，将使用当前页面内容引导下载。")
            return
        self.summary.setText(profile_summary(self.profiles[index]))


def profile_label(profile: dict) -> str:
    tags = ", ".join(profile.get("tags", []))
    return f"{profile.get('name', '未命名配置')}" + (f" [{tags}]" if tags else "")


def profile_summary(profile: dict) -> str:
    keywords = ", ".join(profile.get("filter_keywords", [])) or "无"
    note = profile.get("note", "无")
    return (
        f"备注：{note}\n"
        f"过滤：{'开启' if profile.get('ad_filter') else '关闭'}；关键词：{keywords}\n"
        f"线程：{profile.get('threads', 16)}；保存目录：{profile.get('save_dir', '~/Downloads')}"
    )


def _output_name_for_url(url: str, index: int, current: str) -> str:
    extension = Path(urlparse(url).path).suffix.lower().lstrip(".")
    if not extension or extension in {"m3u", "m3u8", "mpd"} or len(extension) > 5:
        extension = "mp4"
    stem = "video" if current == "video.mp4" else f"video-{index:03d}"
    return f"{stem}.{extension}"


def _looks_like_m3u_url(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in {".m3u8", ".m3u"}
