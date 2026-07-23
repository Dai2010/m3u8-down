from __future__ import annotations

LIGHT_QSS = """
QMainWindow, QDialog { background: #f4f7f5; color: #1e2421; }
QLabel { color: #1e2421; font-weight: 600; }
QLabel#title { font-size: 24px; font-weight: 800; color: __TITLE_COLOR__; }
QLabel#subtitle { font-size: 14px; font-weight: 500; color: #5c665f; }
QCheckBox { color: #1e2421; font-weight: 600; padding: 4px; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #ffffff;
    color: #1e2421;
    border: 1px solid __BORDER_COLOR__;
    border-radius: 6px;
    padding: 8px;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: __BUTTON_COLOR__; }
QComboBox QAbstractItemView { selection-background-color: __BUTTON_COLOR__; selection-color: __BUTTON_TEXT_COLOR__; }
QCheckBox::indicator:checked { background-color: __BUTTON_COLOR__; border: 1px solid __BUTTON_COLOR__; }
QPlainTextEdit#playlistPreview {
    background: #fbf7ec;
    color: #26302b;
    border: 1px solid __PREVIEW_BORDER_COLOR__;
    border-radius: 8px;
    padding: 12px;
    selection-background-color: __BUTTON_COLOR__;
    selection-color: __BUTTON_TEXT_COLOR__;
}
QPushButton {
    background: __BUTTON_COLOR__;
    color: __BUTTON_TEXT_COLOR__;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #8c959f; }
QPushButton#secondary { background: __SECONDARY_BUTTON_COLOR__; color: __SECONDARY_BUTTON_TEXT_COLOR__; }
QPushButton#entry {
    background: #ffffff;
    color: __TITLE_COLOR__;
    border: 1px solid __BORDER_COLOR__;
    border-radius: 8px;
    padding: 22px;
    text-align: left;
    font-size: 17px;
    font-weight: 700;
}
QPushButton#entry:hover { background: __ENTRY_HOVER_BACKGROUND__; border-color: __BUTTON_HOVER_COLOR__; }
QProgressBar {
    background: #ffffff;
    color: #1e2421;
    border: 1px solid __BORDER_COLOR__;
    border-radius: 6px;
    text-align: center;
}
QProgressBar::chunk { background: __BUTTON_COLOR__; border-radius: 5px; }
"""

DARK_QSS = """
QMainWindow, QDialog { background: #171d1a; color: #edf4ef; }
QLabel { color: #edf4ef; font-weight: 600; }
QLabel#title { font-size: 24px; font-weight: 800; color: __TITLE_COLOR__; }
QLabel#subtitle { font-size: 14px; font-weight: 500; color: #aebbb4; }
QCheckBox { color: #edf4ef; font-weight: 600; padding: 4px; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid __BORDER_COLOR__;
    border-radius: 6px;
    padding: 8px;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: __BUTTON_COLOR__; }
QComboBox QAbstractItemView { selection-background-color: __BUTTON_COLOR__; selection-color: __BUTTON_TEXT_COLOR__; }
QCheckBox::indicator:checked { background-color: __BUTTON_COLOR__; border: 1px solid __BUTTON_COLOR__; }
QPlainTextEdit#playlistPreview {
    background: #202820;
    color: #e8ead8;
    border: 1px solid __PREVIEW_BORDER_COLOR__;
    border-radius: 8px;
    padding: 12px;
    selection-background-color: __BUTTON_COLOR__;
    selection-color: __BUTTON_TEXT_COLOR__;
}
QPushButton {
    background: __BUTTON_COLOR__;
    color: __BUTTON_TEXT_COLOR__;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #57606a; }
QPushButton#secondary { background: __SECONDARY_BUTTON_COLOR__; color: __SECONDARY_BUTTON_TEXT_COLOR__; }
QPushButton#entry {
    background: #242c28;
    color: __TITLE_COLOR__;
    border: 1px solid __BORDER_COLOR__;
    border-radius: 8px;
    padding: 22px;
    text-align: left;
    font-size: 17px;
    font-weight: 700;
}
QPushButton#entry:hover { background: __ENTRY_HOVER_BACKGROUND__; border-color: __BUTTON_HOVER_COLOR__; }
QProgressBar {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid __BORDER_COLOR__;
    border-radius: 6px;
    text-align: center;
}
QProgressBar::chunk { background: __BUTTON_COLOR__; border-radius: 5px; }
"""


def stylesheet(is_dark: bool, button_color: str = "") -> str:
    color = button_color or ("#33A383" if is_dark else "#146C5A")
    tokens = _theme_tokens(is_dark, color)
    qss = DARK_QSS if is_dark else LIGHT_QSS
    for token, value in tokens.items():
        qss = qss.replace(token, value)
    return qss


def contrast_text_color(color: str) -> str:
    return "#FFFFFF" if _contrast_ratio(color, "#FFFFFF") >= _contrast_ratio(color, "#111111") else "#111111"


def _theme_tokens(is_dark: bool, color: str) -> dict[str, str]:
    secondary = _mix_color(color, "#6C776F" if is_dark else "#5C665F", 0.58)
    title = _mix_color(color, "#EDF4EF" if is_dark else color, 0.28 if is_dark else 0)
    return {
        "__BUTTON_COLOR__": color,
        "__BUTTON_TEXT_COLOR__": contrast_text_color(color),
        "__BUTTON_HOVER_COLOR__": _mix_color(color, "#FFFFFF" if is_dark else "#F4F7F5", 0.25),
        "__SECONDARY_BUTTON_COLOR__": secondary,
        "__SECONDARY_BUTTON_TEXT_COLOR__": contrast_text_color(secondary),
        "__TITLE_COLOR__": title,
        "__BORDER_COLOR__": _mix_color(color, "#56645D" if is_dark else "#B7C5BD", 0.62),
        "__PREVIEW_BORDER_COLOR__": _mix_color(color, "#55614F" if is_dark else "#D9CDA8", 0.62),
        "__ENTRY_HOVER_BACKGROUND__": _mix_color(color, "#293B34" if is_dark else "#EEF8F3", 0.82),
    }


def _contrast_ratio(color: str, other: str) -> float:
    source = _relative_luminance(color)
    target = _relative_luminance(other)
    lighter = max(source, target)
    darker = min(source, target)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: str) -> float:
    red, green, blue = _rgb(color)
    components = []
    for value in (red, green, blue):
        channel = value / 255
        components.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * components[0] + 0.7152 * components[1] + 0.0722 * components[2]


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
