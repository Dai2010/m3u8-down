from __future__ import annotations

from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config.manager import delete_profile, new_profile, save_profiles, upsert_profile
from ..config.theme import THEME_OPTIONS, normalize_button_color, normalize_theme


class SettingsDialog(QDialog):
    theme_preview_requested = pyqtSignal(str)

    def __init__(self, config: dict, profiles: list[dict] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self._config = config.copy()
        self._initial_theme = normalize_theme(config.get("theme", "system"))
        self.profiles = [profile.copy() for profile in (profiles or [])] or [new_profile("默认配置")]

        self.threads = QSpinBox()
        self.threads.setRange(1, 128)
        self.threads.setValue(int(config.get("threads", 16)))

        self.save_dir = QLineEdit(str(config.get("save_dir", "~/Downloads")))
        browse = QPushButton("选择")
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
        self.theme.addItems(THEME_OPTIONS)
        index = self.theme.findText(str(config.get("theme", "system")))
        self.theme.setCurrentIndex(max(0, index))
        self.theme.currentTextChanged.connect(self._preview_current_theme)
        self.theme.view().setMouseTracking(True)
        self.theme.view().entered.connect(self._preview_hovered_theme)
        self.theme.view().viewport().installEventFilter(self)

        self.button_color = QLineEdit(str(config.get("button_color", "")))
        self.button_color.setPlaceholderText("默认主题色，或 #146C5A")
        color_picker = QPushButton("调色版")
        color_picker.setObjectName("secondary")
        color_picker.clicked.connect(self._choose_button_color)
        color_reset = QPushButton("默认")
        color_reset.setObjectName("secondary")
        color_reset.clicked.connect(lambda: self.button_color.clear())
        color_row = QHBoxLayout()
        color_row.addWidget(self.button_color)
        color_row.addWidget(color_picker)
        color_row.addWidget(color_reset)

        self.general_tab = QWidget()
        general_form = QFormLayout(self.general_tab)
        general_form.addRow("线程数", self.threads)
        general_form.addRow("保存目录", save_dir_row)
        general_form.addRow("Referer", self.referer)
        general_form.addRow("User-Agent", self.user_agent)
        general_form.addRow("过滤关键词", self.keywords)

        self.appearance_tab = QWidget()
        appearance_form = QFormLayout(self.appearance_tab)
        appearance_form.addRow("外观", QLabel("主题与按钮颜色集中在这里。留空按钮色会使用主题默认色。"))
        appearance_form.addRow("主题", self.theme)
        appearance_form.addRow("按钮颜色", color_row)

        self.profiles_tab = self._build_profiles_tab()
        self.about_tab = self._build_about_tab()

        tabs = QTabWidget()
        tabs.addTab(self.general_tab, "常规")
        tabs.addTab(self.appearance_tab, "外观")
        tabs.addTab(self.profiles_tab, "配置管理")
        tabs.addTab(self.about_tab, "关于")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self._refresh_profiles(0)

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
        config["button_color"] = normalize_button_color(self.button_color.text())
        return config

    def accept(self) -> None:
        self._save_current_profile()
        self._config = save_profiles(self.profiles, self.config())
        super().accept()

    def reject(self) -> None:
        self.theme_preview_requested.emit(self._initial_theme)
        super().reject()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.theme.view().viewport() and event.type() == QEvent.Type.Leave:
            self.theme_preview_requested.emit(self.theme.currentText())
        return super().eventFilter(watched, event)

    def _preview_current_theme(self, theme: str) -> None:
        self.theme_preview_requested.emit(theme)

    def _preview_hovered_theme(self, index) -> None:
        if index.isValid():
            self.theme_preview_requested.emit(self.theme.itemText(index.row()))

    def _choose_save_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_dir.text())
        if directory:
            self.save_dir.setText(directory)

    def _choose_button_color(self) -> None:
        current = normalize_button_color(self.button_color.text()) or "#146C5A"
        color = QColorDialog.getColor(QColor(current), self, "选择按钮颜色")
        if color.isValid():
            self.button_color.setText(color.name().upper())

    def _build_profiles_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel("点击配置即可编辑。")
        layout.addWidget(hint)

        body = QHBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self._load_profile)
        body.addWidget(self.profile_list, 1)

        form_column = QVBoxLayout()
        self.profile_name = QLineEdit()
        self.profile_tags = QLineEdit()
        self.profile_note = QTextEdit()
        self.profile_note.setFixedHeight(72)
        self.profile_ad_filter = QPushButton("去广告过滤：关闭")
        self.profile_ad_filter.setCheckable(True)
        self.profile_ad_filter.toggled.connect(lambda checked: self.profile_ad_filter.setText("去广告过滤：开启" if checked else "去广告过滤：关闭"))
        self.profile_keywords = QTextEdit()
        self.profile_keywords.setFixedHeight(96)
        self.profile_threads = QSpinBox()
        self.profile_threads.setRange(1, 128)
        self.profile_save_dir = QLineEdit()
        choose_dir = QPushButton("选择目录")
        choose_dir.setObjectName("secondary")
        choose_dir.clicked.connect(self._choose_profile_dir)
        profile_dir_row = QHBoxLayout()
        profile_dir_row.addWidget(self.profile_save_dir)
        profile_dir_row.addWidget(choose_dir)

        profile_form = QFormLayout()
        profile_form.addRow("名称", self.profile_name)
        profile_form.addRow("标签，逗号分隔", self.profile_tags)
        profile_form.addRow("备注", self.profile_note)
        profile_form.addRow("", self.profile_ad_filter)
        profile_form.addRow("过滤关键词", self.profile_keywords)
        profile_form.addRow("线程数", self.profile_threads)
        profile_form.addRow("保存目录", profile_dir_row)
        form_column.addLayout(profile_form)

        controls = QHBoxLayout()
        save = QPushButton("保存更改")
        save.clicked.connect(self._save_current_profile)
        delete = QPushButton("删除配置")
        delete.setObjectName("secondary")
        delete.clicked.connect(self._delete_profile)
        add = QPushButton("新建配置")
        add.clicked.connect(self._add_profile)
        controls.addStretch(1)
        controls.addWidget(save)
        controls.addWidget(delete)
        controls.addWidget(add)
        form_column.addStretch(1)
        form_column.addLayout(controls)
        body.addLayout(form_column, 2)
        layout.addLayout(body)
        return page

    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("m3u8 Downloader")
        title.setObjectName("title")
        version = QLabel(f"版本：{__version__}")
        links = QLabel(
            '<a href="https://github.com/Dai2010">个人主页</a><br>'
            '<a href="https://github.com/Dai2010/m3u8-down">项目主页</a><br>'
            "协议：GNU General Public License v3.0"
        )
        links.setOpenExternalLinks(True)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(links)
        layout.addStretch(1)
        return page

    def _refresh_profiles(self, selected: int | None = None) -> None:
        current = self.profile_list.currentRow() if selected is None else selected
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for profile in self.profiles:
            QListWidgetItem(self._profile_label(profile), self.profile_list)
        self.profile_list.blockSignals(False)
        if self.profiles:
            self.profile_list.setCurrentRow(max(0, min(current, len(self.profiles) - 1)))
        else:
            self._clear_profile_form()

    def _load_profile(self, index: int) -> None:
        if index < 0 or index >= len(self.profiles):
            self._clear_profile_form()
            return
        profile = self.profiles[index]
        self.profile_name.setText(profile.get("name", ""))
        self.profile_tags.setText(", ".join(profile.get("tags", [])))
        self.profile_note.setPlainText(profile.get("note", ""))
        self.profile_ad_filter.setChecked(bool(profile.get("ad_filter", False)))
        self.profile_keywords.setPlainText("\n".join(profile.get("filter_keywords", [])))
        self.profile_threads.setValue(int(profile.get("threads", 16)))
        self.profile_save_dir.setText(profile.get("save_dir", "~/Downloads"))

    def _save_current_profile(self) -> None:
        index = self.profile_list.currentRow()
        if index < 0:
            return
        self.profiles = upsert_profile(self.profiles, index, self._profile_from_form())
        self._refresh_profiles(index)

    def _add_profile(self) -> None:
        self._save_current_profile()
        self.profiles.append(new_profile(f"配置 {len(self.profiles) + 1}"))
        self._refresh_profiles(len(self.profiles) - 1)

    def _delete_profile(self) -> None:
        index = self.profile_list.currentRow()
        if index < 0:
            return
        if len(self.profiles) <= 1:
            QMessageBox.information(self, "无法删除", "至少保留一个配置。")
            return
        name = self.profiles[index].get("name", "未命名配置")
        answer = QMessageBox.question(self, "删除配置", f"确定删除“{name}”？")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.profiles = delete_profile(self.profiles, index)
        self._refresh_profiles(min(index, len(self.profiles) - 1))

    def _choose_profile_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", self.profile_save_dir.text())
        if directory:
            self.profile_save_dir.setText(directory)

    def _profile_from_form(self) -> dict:
        return {
            "name": self.profile_name.text().strip() or "未命名配置",
            "tags": [tag.strip() for tag in self.profile_tags.text().split(",") if tag.strip()],
            "note": self.profile_note.toPlainText().strip(),
            "ad_filter": self.profile_ad_filter.isChecked(),
            "filter_keywords": [line.strip() for line in self.profile_keywords.toPlainText().splitlines() if line.strip()],
            "threads": self.profile_threads.value(),
            "save_dir": self.profile_save_dir.text().strip() or "~/Downloads",
        }

    def _clear_profile_form(self) -> None:
        self.profile_name.clear()
        self.profile_tags.clear()
        self.profile_note.clear()
        self.profile_ad_filter.setChecked(False)
        self.profile_keywords.clear()
        self.profile_threads.setValue(16)
        self.profile_save_dir.setText("~/Downloads")

    def _profile_label(self, profile: dict) -> str:
        tags = ", ".join(profile.get("tags", []))
        return f"{profile.get('name', '未命名配置')}" + (f" [{tags}]" if tags else "")
