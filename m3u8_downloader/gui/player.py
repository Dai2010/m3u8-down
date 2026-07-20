from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import vlc
except ImportError:
    vlc = None

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget


class VlcUnavailableError(RuntimeError):
    """Raised when the Python or native VLC runtime is unavailable."""


class VideoSurface(QWidget):
    mouse_activity = pyqtSignal()
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)
        self.setStyleSheet("background: #000000;")

    def mouseMoveEvent(self, event) -> None:
        self.mouse_activity.emit()
        super().mouseMoveEvent(event)

    def enterEvent(self, event) -> None:
        self.mouse_activity.emit()
        super().enterEvent(event)

    def mousePressEvent(self, event) -> None:
        self.mouse_activity.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.mouse_activity.emit()
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class VlcPlayerWidget(QWidget):
    fullscreen_requested = pyqtSignal()
    playback_started = pyqtSignal()
    playback_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._instance = None
        self._player = None
        self._media = None
        self._has_media = False

        self.video_surface = VideoSurface(self)
        self.video_surface.mouse_activity.connect(self._show_controls)
        self.video_surface.double_clicked.connect(self.fullscreen_requested.emit)

        self.play_button = QPushButton("播放")
        self.play_button.setObjectName("secondary")
        self.play_button.clicked.connect(self.toggle_play_pause)

        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("secondary")
        self.stop_button.clicked.connect(self.stop)

        self.position_label = QLabel("00:00 / 00:00")
        self.position_label.setMinimumWidth(112)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self._seek_to_position)

        self.speed_box = QComboBox()
        self.speed_box.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_box.setCurrentText("1.0x")
        self.speed_box.currentTextChanged.connect(self._change_speed)

        self.fullscreen_button = QPushButton("全屏")
        self.fullscreen_button.setObjectName("secondary")
        self.fullscreen_button.clicked.connect(self.fullscreen_requested.emit)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 8, 10, 8)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.position_label)
        controls_layout.addWidget(self.seek_slider, 1)
        controls_layout.addWidget(QLabel("倍速"))
        controls_layout.addWidget(self.speed_box)
        controls_layout.addWidget(self.fullscreen_button)

        self.control_bar = QFrame(self)
        self.control_bar.setObjectName("playerControls")
        self.control_bar.setLayout(controls_layout)
        self.control_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.control_bar.setStyleSheet("QFrame#playerControls { background: rgba(25, 25, 25, 225); border-radius: 6px; }")

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_surface, 0, 0)
        layout.addWidget(self.control_bar, 0, 0, Qt.AlignmentFlag.AlignBottom)
        self.control_bar.raise_()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(5000)
        self._hide_timer.timeout.connect(self._hide_controls)

        self._update_timer = QTimer(self)
        self._update_timer.setInterval(250)
        self._update_timer.timeout.connect(self._update_playback_state)
        self._install_mouse_tracking(self)
        self.setMinimumHeight(280)
        self._set_playback_controls(False)

    def play(self, url: str, headers: dict[str, str] | None = None) -> None:
        if not url:
            raise VlcUnavailableError("播放地址为空")
        self._ensure_player()
        self.stop()
        self._media = self._instance.media_new(url)
        for name, value in (headers or {}).items():
            if not value:
                continue
            option_name = {"Referer": ":http-referrer", "User-Agent": ":http-user-agent"}.get(name)
            if option_name:
                self._media.add_option(f"{option_name}={value}")
        self._player.set_media(self._media)
        self._set_video_window()
        result = self._player.play()
        if result == -1:
            raise VlcUnavailableError("VLC 无法开始播放媒体")
        self._has_media = True
        self._set_playback_controls(True)
        self._show_controls()
        self._update_timer.start()
        self.playback_started.emit()

    def toggle_play_pause(self) -> None:
        if not self._player or not self._has_media:
            return
        if self._player.is_playing():
            self._player.pause()
            self.play_button.setText("播放")
            self._hide_timer.stop()
            self._show_controls()
        else:
            self._player.play()
            self.play_button.setText("暂停")
            self._show_controls()

    def stop(self) -> None:
        if self._player and self._has_media:
            self._player.stop()
        self._has_media = False
        self._update_timer.stop()
        self._hide_timer.stop()
        self.seek_slider.setValue(0)
        self.position_label.setText("00:00 / 00:00")
        self._set_playback_controls(False)
        self._show_controls()
        self.playback_stopped.emit()

    def close(self) -> None:
        self.stop()
        if self._player:
            self._player.release()
            self._player = None
        if self._instance:
            self._instance.release()
            self._instance = None

    def _ensure_player(self) -> None:
        if vlc is None:
            raise VlcUnavailableError("未安装 python-vlc，请安装桌面端依赖")
        if self._player:
            return
        _configure_vlc_runtime()
        try:
            self._instance = vlc.Instance("--no-video-title-show")
            if self._instance is None:
                raise VlcUnavailableError("找不到 libVLC 运行库")
            self._player = self._instance.media_player_new()
        except Exception as exc:
            self._instance = None
            raise VlcUnavailableError(f"无法初始化 VLC：{exc}") from exc

    def _set_video_window(self) -> None:
        if not self._player:
            return
        window_id = int(self.video_surface.winId())
        if sys.platform.startswith("win"):
            self._player.set_hwnd(window_id)
        elif sys.platform == "darwin":
            self._player.set_nsobject(window_id)
        else:
            self._player.set_xwindow(window_id)

    def _seek_to_position(self, value: int) -> None:
        if self._player and self._has_media:
            self._player.set_position(value / 1000.0)

    def _change_speed(self, value: str) -> None:
        if self._player and self._has_media:
            self._player.set_rate(float(value.rstrip("x")))

    def _update_playback_state(self) -> None:
        if not self._player or not self._has_media:
            return
        length = self._player.get_length()
        current = self._player.get_time()
        if length > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(max(0, min(1000, int(current / length * 1000))))
            self.seek_slider.blockSignals(False)
        self.position_label.setText(f"{_format_time(current)} / {_format_time(length)}")
        playing = self._player.is_playing()
        self.play_button.setText("暂停" if playing else "播放")
        if playing and self.control_bar.isVisible() and not self._hide_timer.isActive():
            self._hide_timer.start()
        elif not playing:
            self._hide_timer.stop()
            self.control_bar.show()

    def _set_playback_controls(self, enabled: bool) -> None:
        self.play_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.seek_slider.setEnabled(enabled)
        self.speed_box.setEnabled(enabled)

    def _show_controls(self) -> None:
        self.control_bar.show()
        self.control_bar.raise_()
        self._hide_timer.stop()
        if self._player and self._player.is_playing():
            self._hide_timer.start()

    def _hide_controls(self) -> None:
        if self._player and self._player.is_playing():
            self.control_bar.hide()

    def _install_mouse_tracking(self, widget: QObject) -> None:
        if isinstance(widget, QWidget):
            widget.setMouseTracking(True)
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            if child is not self:
                self._install_mouse_tracking(child)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.MouseMove, QEvent.Type.Enter, QEvent.Type.MouseButtonPress}:
            self._show_controls()
        return super().eventFilter(watched, event)


def _configure_vlc_runtime() -> None:
    if not sys.platform.startswith("win"):
        return
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    candidates = [base / "vlc", base]
    for directory in candidates:
        if not (directory / "libvlc.dll").exists():
            continue
        os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
        plugins = directory / "plugins"
        if plugins.exists():
            os.environ["VLC_PLUGIN_PATH"] = str(plugins)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(directory))
        break


def _format_time(milliseconds: int) -> str:
    if milliseconds < 0:
        return "00:00"
    seconds = milliseconds // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
