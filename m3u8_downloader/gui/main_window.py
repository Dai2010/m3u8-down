from __future__ import annotations

import shutil
import asyncio
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
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
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config.manager import delete_profile, load_config, load_profiles, new_profile, save_profiles, upsert_profile
from ..core.downloader import Downloader
from ..core.filter import filter_playlist
from ..core.merger import merge_to_mp4
from ..core.proxy_server import ProxyServer
from ..core.utils import expand_path, require_ffmpeg
from ..main import _load_media_playlist
from .settings_dialog import SettingsDialog
from .theme import apply_gui_theme
from .windows_dependencies import ensure_ffmpeg as ensure_windows_ffmpeg


@dataclass
class DownloadTask:
    url: str
    output_name: str


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

            require_ffmpeg()
            for task_index, task in enumerate(self.tasks, start=1):
                if self._cancelled:
                    raise RuntimeError("download cancelled")
                output = self.output_dir / task.output_name
                work_dir = work_root / str(task_index)
                self.log.emit(f"[{task_index}/{len(self.tasks)}] Loading playlist")
                playlist = _load_media_playlist(task.url, headers)
                filtered = filter_playlist(playlist, keywords)
                if not filtered.segments:
                    raise RuntimeError("no playable segments after filtering")

                self.log.emit(f"[{task_index}/{len(self.tasks)}] Downloading {len(filtered.segments)} segments")
                downloader = Downloader(threads=threads, headers=headers)
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
        self.resize(900, 620)
        self.config = load_config()
        self.profiles = load_profiles(self.config)
        self.active_profile = self.profiles[0]
        self.worker: DownloadWorker | None = None
        self.proxy_worker: ProxyWorker | None = None
        self.download_rows: list[tuple[QLineEdit, QLineEdit, QWidget]] = []

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
        tasks = self._download_tasks()
        if not tasks:
            QMessageBox.warning(self, "Missing URL", "Add at least one m3u8 URL.")
            return
        output_dir = expand_path(self.output.text().strip())
        if not ensure_windows_ffmpeg(self):
            return
        config = self._runtime_config(
            self.download_referer.text().strip(),
            self.download_ad_filter.isChecked(),
            self.download_keywords.toPlainText(),
            self.download_threads.value(),
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
            QMessageBox.warning(self, "Missing URL", "Enter an m3u8 URL.")
            return
        config = self._runtime_config(
            self.stream_referer.text().strip(),
            self.stream_ad_filter.isChecked(),
            self.stream_keywords.toPlainText(),
        )
        self.proxy_button.setEnabled(False)
        self.stop_proxy_button.setEnabled(True)
        self.proxy_worker = ProxyWorker(url, config, self)
        self.proxy_worker.started_url.connect(self._proxy_started)
        self.proxy_worker.failed.connect(self._proxy_failed)
        self.proxy_worker.start()

    def _stop_proxy(self) -> None:
        if self.proxy_worker:
            self.proxy_worker.stop()
            self.proxy_worker = None
        self.proxy_button.setEnabled(True)
        self.stop_proxy_button.setEnabled(False)
        self._append_stream_log("Proxy stopped")

    def _proxy_started(self, proxy_url: str) -> None:
        self._append_stream_log(f"Proxy URL: {proxy_url}")
        self.stream_status.setText("Proxy running")

    def _proxy_failed(self, message: str) -> None:
        self._append_stream_log(f"Proxy failed: {message}")
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
            app = QApplication.instance()
            if app is not None:
                apply_gui_theme(app, self.config.get("theme", "system"))
            referer = self.config.get("headers", {}).get("Referer", "")
            self.stream_referer.setText(referer)
            self.download_referer.setText(referer)
            self.download_threads.setValue(int(self.config.get("threads", 16)))
            self._append_log("Settings saved")

    def _open_profiles(self) -> None:
        dialog = ProfileDialog(self.profiles, self)
        if dialog.exec():
            self.profiles = dialog.profiles
            self.config = save_profiles(self.profiles, self.config)
            self.active_profile = self.profiles[0]
            self._apply_profile(self.active_profile)

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

    def _add_download_row(self, url: str = "", output_name: str = "video.mp4") -> None:
        row_widget = QWidget()
        layout = QVBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        url_row = QHBoxLayout()
        url_edit = QLineEdit(url)
        url_edit.setPlaceholderText("https://example.com/video/index.m3u8")
        remove = QPushButton("删除")
        remove.setObjectName("secondary")
        url_row.addWidget(url_edit)
        url_row.addWidget(remove)
        output_edit = QLineEdit(output_name)
        output_edit.setPlaceholderText("video.mp4")
        output_edit.setStyleSheet("margin-left: 28px;")
        layout.addLayout(url_row)
        layout.addWidget(output_edit)
        self.download_rows_layout.addWidget(row_widget)
        self.download_rows.append((url_edit, output_edit, row_widget))
        remove.clicked.connect(lambda: self._remove_download_row(row_widget))

    def _remove_download_row(self, row_widget: QWidget) -> None:
        self.download_rows = [row for row in self.download_rows if row[2] is not row_widget]
        row_widget.setParent(None)
        row_widget.deleteLater()

    def _download_tasks(self) -> list[DownloadTask]:
        tasks: list[DownloadTask] = []
        for index, (url_edit, output_edit, _) in enumerate(self.download_rows, start=1):
            url = url_edit.text().strip()
            if not url:
                continue
            output_name = output_edit.text().strip() or f"video-{index:03d}.mp4"
            tasks.append(DownloadTask(url, output_name))
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

        stream = QPushButton("流播\n直接播放 m3u8，可按需开启去广告过滤。")
        stream.setObjectName("entry")
        stream.clicked.connect(lambda: self.stack.setCurrentWidget(self.stream_page))
        download = QPushButton("下载\n保存为 MP4，可按需开启去广告过滤。")
        download.setObjectName("entry")
        download.clicked.connect(lambda: self.stack.setCurrentWidget(self.download_page))
        profiles = QPushButton("管理配置\n新建、修改或删除过滤、线程、目录和标签。")
        profiles.setObjectName("entry")
        profiles.clicked.connect(self._open_profiles)
        about = QPushButton("关于\n查看作者主页、项目主页和协议。")
        about.setObjectName("entry")
        about.clicked.connect(self._show_about)
        layout.addWidget(stream)
        layout.addWidget(download)
        layout.addWidget(profiles)
        layout.addWidget(about)
        layout.addStretch(1)
        return page

    def _build_stream_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addLayout(self._header_row("流播"))

        self.stream_url = QLineEdit()
        self.stream_url.setPlaceholderText("https://example.com/video/index.m3u8")
        self.stream_referer = QLineEdit(self.config.get("headers", {}).get("Referer", ""))
        self.stream_ad_filter = QCheckBox("启用去广告过滤")
        self.stream_ad_filter.toggled.connect(self._sync_filter_visibility)
        self.stream_keywords = QTextEdit("\n".join(self.config.get("filter_keywords", [])))
        self.stream_keywords.setFixedHeight(96)
        self.stream_keywords_label = QLabel("过滤关键词，每行一个")

        form = QFormLayout()
        form.addRow("m3u8 地址", self.stream_url)
        form.addRow("Referer，可留空", self.stream_referer)
        form.addRow("", self.stream_ad_filter)
        form.addRow(self.stream_keywords_label, self.stream_keywords)
        layout.addLayout(form)

        self.proxy_button = QPushButton("开始流播")
        self.proxy_button.clicked.connect(self._start_proxy)
        self.stop_proxy_button = QPushButton("停止流播")
        self.stop_proxy_button.setObjectName("secondary")
        self.stop_proxy_button.setEnabled(False)
        self.stop_proxy_button.clicked.connect(self._stop_proxy)
        controls = QHBoxLayout()
        controls.addWidget(self.proxy_button)
        controls.addWidget(self.stop_proxy_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.stream_status = QLabel("等待操作")
        self.stream_log = QTextEdit()
        self.stream_log.setReadOnly(True)
        layout.addWidget(self.stream_status)
        layout.addWidget(self.stream_log, 1)
        return page

    def _build_download_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addLayout(self._header_row("下载"))

        self.download_referer = QLineEdit(self.config.get("headers", {}).get("Referer", ""))
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
        self.download_keywords = QTextEdit("\n".join(self.active_profile.get("filter_keywords", self.config.get("filter_keywords", []))))
        self.download_keywords.setFixedHeight(96)
        self.download_keywords_label = QLabel("过滤关键词，每行一个")
        self.download_rows_layout = QVBoxLayout()
        add_url = QPushButton("添加 URL")
        add_url.setObjectName("secondary")
        add_url.clicked.connect(lambda: self._add_download_row(output_name=f"video-{len(self.download_rows) + 1:03d}.mp4"))

        form = QFormLayout()
        form.addRow("Referer，可留空", self.download_referer)
        form.addRow("保存目录", output_row)
        form.addRow("并发线程数", self.download_threads)
        form.addRow("", self.download_ad_filter)
        form.addRow(self.download_keywords_label, self.download_keywords)
        layout.addLayout(form)
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

    def _runtime_config(self, referer: str, ad_filter: bool, keywords_text: str, threads: int | None = None) -> dict:
        config = self.config.copy()
        headers = config.get("headers", {}).copy()
        headers["Referer"] = referer
        config["headers"] = headers
        config["filter_keywords"] = [line.strip() for line in keywords_text.splitlines() if line.strip()] if ad_filter else []
        if threads is not None:
            config["threads"] = threads
        return config

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 m3u8 Downloader",
            "m3u8 Downloader\n\n"
            "作者主页：https://github.com/Dai2010\n"
            "项目主页：https://github.com/Dai2010/m3u8-down\n"
            "协议：GNU General Public License v3.0",
        )


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


class ProfileDialog(QDialog):
    def __init__(self, profiles: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理配置")
        self.profiles = [profile.copy() for profile in profiles]
        layout = QHBoxLayout(self)
        self.list_widget = QListWidget()
        form_column = QVBoxLayout()
        self.name = QLineEdit()
        self.tags = QLineEdit()
        self.note = QTextEdit()
        self.note.setFixedHeight(72)
        self.ad_filter = QCheckBox("启用去广告过滤")
        self.keywords = QTextEdit()
        self.keywords.setFixedHeight(96)
        self.threads = QSpinBox()
        self.threads.setRange(1, 128)
        self.save_dir = QLineEdit()
        choose_dir = QPushButton("选择目录")
        choose_dir.clicked.connect(self._choose_dir)
        row = QHBoxLayout()
        row.addWidget(self.save_dir)
        row.addWidget(choose_dir)
        form = QFormLayout()
        form.addRow("名称", self.name)
        form.addRow("标签，逗号分隔", self.tags)
        form.addRow("备注", self.note)
        form.addRow("", self.ad_filter)
        form.addRow("过滤关键词", self.keywords)
        form.addRow("线程数", self.threads)
        form.addRow("保存目录", row)
        add = QPushButton("新增配置")
        add.clicked.connect(self._add_profile)
        save = QPushButton("保存当前配置")
        save.clicked.connect(self._save_current)
        delete = QPushButton("删除当前配置")
        delete.setObjectName("secondary")
        delete.clicked.connect(self._delete_current)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form_column.addLayout(form)
        form_column.addWidget(add)
        form_column.addWidget(save)
        form_column.addWidget(delete)
        form_column.addWidget(buttons)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(form_column, 2)
        self.list_widget.currentRowChanged.connect(self._load_profile)
        self._refresh()

    def accept(self) -> None:
        self._save_current()
        super().accept()

    def _refresh(self) -> None:
        self.list_widget.clear()
        for profile in self.profiles:
            QListWidgetItem(profile_label(profile), self.list_widget)
        if self.profiles:
            self.list_widget.setCurrentRow(0)

    def _load_profile(self, index: int) -> None:
        if index < 0 or index >= len(self.profiles):
            return
        profile = self.profiles[index]
        self.name.setText(profile.get("name", ""))
        self.tags.setText(", ".join(profile.get("tags", [])))
        self.note.setPlainText(profile.get("note", ""))
        self.ad_filter.setChecked(bool(profile.get("ad_filter", False)))
        self.keywords.setPlainText("\n".join(profile.get("filter_keywords", [])))
        self.threads.setValue(int(profile.get("threads", 16)))
        self.save_dir.setText(profile.get("save_dir", "~/Downloads"))

    def _save_current(self) -> None:
        index = self.list_widget.currentRow()
        if index < 0:
            return
        self.profiles = upsert_profile(self.profiles, index, self._form_profile())
        self._refresh()
        self.list_widget.setCurrentRow(index)

    def _add_profile(self) -> None:
        profile = new_profile(f"配置 {len(self.profiles) + 1}")
        self.profiles.append(profile)
        self._refresh()
        self.list_widget.setCurrentRow(len(self.profiles) - 1)

    def _delete_current(self) -> None:
        index = self.list_widget.currentRow()
        if index < 0:
            return
        if len(self.profiles) <= 1:
            QMessageBox.information(self, "无法删除", "至少保留一个配置。")
            return
        name = self.profiles[index].get("name", "未命名配置")
        answer = QMessageBox.question(self, "删除配置", f"确定删除“{name}”？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profiles = delete_profile(self.profiles, index)
        self._refresh()
        self.list_widget.setCurrentRow(min(index, len(self.profiles) - 1))

    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_dir.text())
        if path:
            self.save_dir.setText(path)

    def _form_profile(self) -> dict:
        return {
            "name": self.name.text().strip() or "未命名配置",
            "tags": [tag.strip() for tag in self.tags.text().split(",") if tag.strip()],
            "note": self.note.toPlainText().strip(),
            "ad_filter": self.ad_filter.isChecked(),
            "filter_keywords": [line.strip() for line in self.keywords.toPlainText().splitlines() if line.strip()],
            "threads": self.threads.value(),
            "save_dir": self.save_dir.text().strip() or "~/Downloads",
        }


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
