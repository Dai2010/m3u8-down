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
QPushButton {
    background: #146c5a;
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
QPushButton#entry:hover { background: #eef8f3; border-color: #6fb39d; }
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
QPushButton {
    background: #33a383;
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
QPushButton#entry:hover { background: #293b34; border-color: #45c79d; }
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
