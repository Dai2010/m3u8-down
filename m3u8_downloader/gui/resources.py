from __future__ import annotations

LIGHT_QSS = """
QMainWindow, QDialog { background: #f6f7f9; color: #1f2328; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #ffffff;
    border: 1px solid #c9d1d9;
    border-radius: 4px;
    padding: 6px;
}
QPushButton {
    background: #1f6feb;
    color: #ffffff;
    border: 0;
    border-radius: 4px;
    padding: 7px 12px;
}
QPushButton:disabled { background: #8c959f; }
QPushButton#secondary { background: #57606a; }
QProgressBar {
    background: #ffffff;
    border: 1px solid #c9d1d9;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk { background: #2da44e; border-radius: 3px; }
"""

DARK_QSS = """
QMainWindow, QDialog { background: #202124; color: #e6edf3; }
QLineEdit, QTextEdit, QSpinBox, QComboBox {
    background: #2d3137;
    color: #e6edf3;
    border: 1px solid #57606a;
    border-radius: 4px;
    padding: 6px;
}
QPushButton {
    background: #2f81f7;
    color: #ffffff;
    border: 0;
    border-radius: 4px;
    padding: 7px 12px;
}
QPushButton:disabled { background: #57606a; }
QPushButton#secondary { background: #6e7681; }
QProgressBar {
    background: #2d3137;
    border: 1px solid #57606a;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk { background: #3fb950; border-radius: 3px; }
"""


def stylesheet(is_dark: bool) -> str:
    return DARK_QSS if is_dark else LIGHT_QSS
