from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QStyleFactory

from .main_window import MainWindow
from .resources import stylesheet


def main() -> None:
    app = QApplication(sys.argv)
    _configure_desktop(app)
    window = MainWindow()
    window.show()
    raise SystemExit(app.exec())


def _configure_desktop(app: QApplication) -> None:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    styles = {style.lower(): style for style in QStyleFactory.keys()}
    if "gnome" in desktop and "gtk3" in styles:
        app.setStyle(styles["gtk3"])
    else:
        app.setStyle(styles.get("fusion", app.style().objectName()))

    if "gnome" in desktop:
        QIcon.setThemeName("Adwaita")
    elif "kde" in desktop:
        QIcon.setThemeName("breeze")

    color_scheme = getattr(app.styleHints(), "colorScheme", None)
    is_dark = bool(color_scheme and color_scheme() == Qt.ColorScheme.Dark)
    app.setStyleSheet(stylesheet(is_dark))


if __name__ == "__main__":
    main()
