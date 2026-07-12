from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from ..config.manager import load_config
from .main_window import MainWindow
from .theme import apply_gui_theme, configure_platform_style


def main() -> None:
    app = QApplication(sys.argv)
    _configure_desktop(app)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


def _configure_desktop(app: QApplication) -> None:
    if os.name == "nt":
        _set_windows_app_id()

    icon_path = _resource_path("m3u8-downloader.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    configure_platform_style(app)
    apply_gui_theme(app, load_config().get("theme", "system"))


def _resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def _set_windows_app_id() -> None:
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dai2010.m3u8Downloader")
    except Exception:
        pass


if __name__ == "__main__":
    main()
