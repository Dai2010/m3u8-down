from __future__ import annotations

LIGHT_QSS = """
QMainWindow, QDialog { background: #f4f7f5; color: #1e2421; }
QLabel { color: #1e2421; font-weight: 600; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #ffffff;
    color: #1e2421;
    border: 1px solid #b7c5bd;
    border-radius: 6px;
    padding: 8px;
}
QPushButton {
    background: #146c5a;
    color: #ffffff;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #8c959f; }
QPushButton#secondary { background: #5c665f; }
QProgressBar {
    background: #ffffff;
    color: #1e2421;
    border: 1px solid #b7c5bd;
    border-radius: 6px;
    text-align: center;
}
QProgressBar::chunk { background: #2f8f72; border-radius: 5px; }
"""

DARK_QSS = """
QMainWindow, QDialog { background: #171d1a; color: #edf4ef; }
QLabel { color: #edf4ef; font-weight: 600; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid #56645d;
    border-radius: 6px;
    padding: 8px;
}
QPushButton {
    background: #33a383;
    color: #ffffff;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #57606a; }
QPushButton#secondary { background: #6c776f; }
QProgressBar {
    background: #242c28;
    color: #edf4ef;
    border: 1px solid #56645d;
    border-radius: 6px;
    text-align: center;
}
QProgressBar::chunk { background: #45c79d; border-radius: 5px; }
"""


def stylesheet(is_dark: bool) -> str:
    return DARK_QSS if is_dark else LIGHT_QSS
