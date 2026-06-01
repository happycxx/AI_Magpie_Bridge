"""Version management dialog."""
import os
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QMessageBox)
from .widgets import DiffDialog
from app.i18n import DEFAULT_LANGUAGE, translate


class VersionManagerDialog(QDialog):
    def _t(self, key, fallback="", **kwargs):
        if self.main_window and hasattr(self.main_window, "tr_text"):
            try:
                return self.main_window.tr_text(key, **kwargs)
            except Exception:
                pass

        language = getattr(self.main_window, "current_language", DEFAULT_LANGUAGE) if self.main_window else DEFAULT_LANGUAGE
        text = translate(key, language, **kwargs)
        if text == key and fallback:
            if kwargs:
                try:
                    return fallback.format(**kwargs)
                except Exception:
                    return fallback
            return fallback
        return text

    def __init__(self, current_file_path, current_code, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle(self._t("version.title", "关键版本管理"))
        self.resize(550, 400)
        self.current_file_path = current_file_path
        self.current_code = current_code

        layout = QVBoxLayout(self)

        if not current_file_path:
            layout.addWidget(QLabel(self._t(
                "version.no_file",
                "当前没有打开任何文件，无法查看关联版本。")))
            return

        self.lbl_info = QLabel(self._t(
            "version.current_file",
            "当前关联文件: {file_name}",
            file_name=os.path.basename(current_file_path)))
        self.lbl_info.setStyleSheet(
            "font-weight: bold; color: #303133; margin-bottom: 5px;")
        layout.addWidget(self.lbl_info)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { font-size: 14px; padding: 5px; } "
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #EBEEF5; } "
            "QListWidget::item:selected { background-color: #ECF5FF; color: #409EFF; }")
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.btn_diff = QPushButton(self._t(
            "version.btn.diff",
            "🔍 与当前代码对比"))
        self.btn_diff.clicked.connect(self.compare_version)
        self.btn_load = QPushButton(self._t(
            "version.btn.load",
            "📂 加载选中版本"))
        self.btn_load.clicked.connect(self.load_version)
        self.btn_delete = QPushButton(self._t(
            "version.btn.delete",
            "🗑️ 删除选中版本"))
        self.btn_delete.clicked.connect(self.delete_version)

        btn_layout.addWidget(self.btn_diff)
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_layout)

        self.versions = []
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        self.versions.clear()
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.backup_dir = os.path.join(app_dir, "key_versions")
        json_path = os.path.join(self.backup_dir, "versions_info.json")

        if not os.path.exists(json_path):
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
        except Exception:
            return

        file_versions = info.get(self.current_file_path, [])
        file_versions.sort(key=lambda x: x.get("time", ""), reverse=True)
        self.versions = file_versions

        for v in self.versions:
            if os.path.exists(os.path.join(self.backup_dir, v["filename"])):
                self.list_widget.addItem(f"🕒 {v['time']}  |  📄 {v['filename']}")

    def get_selected_version(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.versions):
            QMessageBox.warning(
                self,
                self._t("tab.notice.title", "提示"),
                self._t("version.select_required", "请先选中一个版本！"))
            return None
        return self.versions[row]

    def compare_version(self):
        v = self.get_selected_version()
        if not v:
            return
        file_path = os.path.join(self.backup_dir, v["filename"])
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                version_code = f.read().splitlines(keepends=True)
        except Exception as e:
            QMessageBox.critical(
                self,
                self._t("version.read_failed.title", "错误"),
                self._t("version.read_failed.message", "无法读取版本文件: {error}", error=e))
            return

        import difflib
        current_lines = self.current_code.splitlines(keepends=True)
        diff = difflib.unified_diff(
            version_code,
            current_lines,
            fromfile=self._t("version.diff.from", "版本: {time}", time=v["time"]),
            tofile=self._t("version.diff.to", "当前编辑器代码"))
        diff_text = "".join(diff)
        if not diff_text:
            diff_text = self._t(
                "version.diff.no_change",
                "该版本与当前编辑器中的代码完全一致。")

        dialog = DiffDialog(diff_text, self)
        dialog.exec()

    def load_version(self):
        v = self.get_selected_version()
        if not v:
            return
        file_path = os.path.join(self.backup_dir, v["filename"])
        if self.main_window:
            self.main_window.open_file_in_tab(file_path)
            self.accept()

    def delete_version(self):
        v = self.get_selected_version()
        if not v:
            return
        reply = QMessageBox.question(
            self,
            self._t("version.delete.confirm.title", "确认删除"),
            self._t(
                "version.delete.confirm.message",
                "确定要永久删除版本 {file_name} 吗？",
                file_name=v["filename"]),
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            file_path = os.path.join(self.backup_dir, v["filename"])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                json_path = os.path.join(self.backup_dir, "versions_info.json")
                with open(json_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                info[self.current_file_path] = [
                    item for item in info.get(self.current_file_path, [])
                    if item["filename"] != v["filename"]
                ]
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=4)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    self._t("version.delete.failed.title", "错误"),
                    self._t("version.delete.failed.message", "删除失败: {error}", error=e))
