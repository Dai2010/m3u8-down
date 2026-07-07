from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from ..config.manager import save_config


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._config = config.copy()

        self.threads = QSpinBox()
        self.threads.setRange(1, 128)
        self.threads.setValue(int(config.get("threads", 16)))

        self.save_dir = QLineEdit(str(config.get("save_dir", "~/Downloads")))
        browse = QPushButton("Browse")
        browse.setObjectName("secondary")
        browse.clicked.connect(self._choose_save_dir)
        save_dir_row = QHBoxLayout()
        save_dir_row.addWidget(self.save_dir)
        save_dir_row.addWidget(browse)

        headers = config.get("headers", {})
        self.referer = QLineEdit(headers.get("Referer", ""))
        self.user_agent = QLineEdit(headers.get("User-Agent", ""))

        self.keywords = QTextEdit("\n".join(config.get("filter_keywords", [])))
        self.keywords.setFixedHeight(96)

        self.theme = QComboBox()
        self.theme.addItems(["system", "light", "dark"])
        index = self.theme.findText(str(config.get("theme", "system")))
        self.theme.setCurrentIndex(max(0, index))

        form = QFormLayout()
        form.addRow("Threads", self.threads)
        form.addRow("Save directory", save_dir_row)
        form.addRow("Referer", self.referer)
        form.addRow("User-Agent", self.user_agent)
        form.addRow("Filter keywords", self.keywords)
        form.addRow("Theme", self.theme)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def config(self) -> dict:
        config = self._config.copy()
        config["threads"] = self.threads.value()
        config["save_dir"] = self.save_dir.text().strip() or "~/Downloads"
        config["headers"] = {
            "Referer": self.referer.text().strip(),
            "User-Agent": self.user_agent.text().strip(),
        }
        config["filter_keywords"] = [line.strip() for line in self.keywords.toPlainText().splitlines() if line.strip()]
        config["theme"] = self.theme.currentText()
        return config

    def accept(self) -> None:
        save_config(self.config())
        super().accept()

    def _choose_save_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose save directory", self.save_dir.text())
        if directory:
            self.save_dir.setText(directory)
