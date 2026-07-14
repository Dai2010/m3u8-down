from __future__ import annotations

LIGHT_QSS = """
QMainWindow, QDialog { background: #f4f7f5; color: #1e2421; }
QLabel { color: #1e2421; font-weight: 600; }
QLabel#title { font-size: 24px; font-weight: 800; color: #12352d; }
QLabel#subtitle { font-size: 14px; font-weight: 500; color: #5c665f; }
QCheckBox { color: #1e2421; font-weight: 600; padding: 4px; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #ffffff;
    color: #1e2421;
    border: 1px solid #b7c5bd;
    border-radius: 6px;
    padding: 8px;
}
QPlainTextEdit#playlistPreview {
    background: #fbf7ec;
    color: #26302b;
    border: 1px solid #d9cda8;
    border-radius: 8px;
    padding: 12px;
    selection-background-color: __BUTTON_COLOR__;
    selection-color: #ffffff;
}
QPushButton {
    background: __BUTTON_COLOR__;
    color: #ffffff;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #8c959f; }
QPushButton#secondary { background: #5c665f; }
QPushButton#entry {
    background: #ffffff;
    color: #12352d;
    border: 1px solid #c7d4cd;
    border-radius: 8px;
    padding: 22px;
    text-align: left;
    font-size: 17px;
    font-weight: 700;
}
QPushButton#entry:hover { background: #eef8f3; border-color: __BUTTON_HOVER_COLOR__; }
QProgressBar {
    background: #ffffff;
    color: #1e2421;
    border: 1px solid #b7c5bd;
    border-radius: 6px;
    text-align: center;
}
QProgressBar::chunk { background: __BUTTON_COLOR__; border-radius: 5px; }
"""

DARK_QSS = """
QMainWindow, QDialog { background: #171d1a; color: #edf4ef; }
QLabel { color: #edf4ef; font-weight: 600; }
QLabel#title { font-size: 24px; font-weight: 800; color: #edf4ef; }
QLabel#subtitle { font-size: 14px; font-weight: 500; color: #aebbb4; }
QCheckBox { color: #edf4ef; font-weight: 600; padding: 4px; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid #56645d;
    border-radius: 6px;
    padding: 8px;
}
QPlainTextEdit#playlistPreview {
    background: #202820;
    color: #e8ead8;
    border: 1px solid #55614f;
    border-radius: 8px;
    padding: 12px;
    selection-background-color: __BUTTON_COLOR__;
    selection-color: #101815;
}
QPushButton {
    background: __BUTTON_COLOR__;
    color: #ffffff;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #57606a; }
QPushButton#secondary { background: #6c776f; }
QPushButton#entry {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid #56645d;
    border-radius: 8px;
    padding: 22px;
    text-align: left;
    font-size: 17px;
    font-weight: 700;
}
QPushButton#entry:hover { background: #293b34; border-color: __BUTTON_HOVER_COLOR__; }
QProgressBar {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid #56645d;
    border-radius: 6px;
    text-align: center;
}
QProgressBar::chunk { background: __BUTTON_COLOR__; border-radius: 5px; }
"""


def stylesheet(is_dark: bool, button_color: str = "") -> str:
    color = button_color or ("#33a383" if is_dark else "#146c5a")
    return (DARK_QSS if is_dark else LIGHT_QSS).replace("__BUTTON_COLOR__", color).replace(
        "__BUTTON_HOVER_COLOR__",
        _mix_color(color, "#ffffff" if is_dark else "#f4f7f5", 0.25),
    )


def _mix_color(color: str, other: str, ratio: float) -> str:
    try:
        source = _rgb(color)
        target = _rgb(other)
    except ValueError:
        return color
    mixed = [round(source[index] * (1 - ratio) + target[index] * ratio) for index in range(3)]
    return "#" + "".join(f"{value:02X}" for value in mixed)


def _rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("expected #RRGGBB color")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
