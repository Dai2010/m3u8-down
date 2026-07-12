from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory

from ..config.theme import normalize_theme, should_use_dark_theme
from .resources import stylesheet


def configure_platform_style(app: QApplication) -> None:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    styles = {style.lower(): style for style in QStyleFactory.keys()}
    if "gnome" in desktop and "gtk3" in styles:
        app.setStyle(styles["gtk3"])
    else:
        app.setStyle(styles.get("fusion", app.style().objectName()))

    if "gnome" in desktop:
        from PyQt6.QtGui import QIcon

        QIcon.setThemeName("Adwaita")
    elif "kde" in desktop:
        from PyQt6.QtGui import QIcon

        QIcon.setThemeName("breeze")


def apply_gui_theme(app: QApplication, preference: object = "system") -> None:
    theme = normalize_theme(preference)
    is_dark = _qt_prefers_dark(app) if theme == "system" else None
    if is_dark is None:
        is_dark = should_use_dark_theme(theme)
    app.setPalette(_palette(is_dark))
    app.setStyleSheet(stylesheet(is_dark))


def _qt_prefers_dark(app: QApplication) -> bool | None:
    color_scheme = getattr(app.styleHints(), "colorScheme", None)
    if color_scheme is None:
        return None
    try:
        return color_scheme() == Qt.ColorScheme.Dark
    except Exception:
        return None


def _palette(is_dark: bool) -> QPalette:
    palette = QPalette()
    if is_dark:
        palette.setColor(QPalette.ColorRole.Window, QColor("#171d1a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#edf4ef"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#242c28"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1d2420"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#242c28"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#edf4ef"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#edf4ef"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#242c28"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#edf4ef"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#45c79d"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#092d24"))
        return palette

    palette.setColor(QPalette.ColorRole.Window, QColor("#f4f7f5"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1e2421"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#eef8f3"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1e2421"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1e2421"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1e2421"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2f8f72"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return palette
