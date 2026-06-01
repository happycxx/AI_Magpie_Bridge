"""TabManagerMixin — file/tab open, close, switch, reload, and version management."""
import os
import datetime
import json
import difflib
from PySide6.QtWidgets import QMessageBox, QFileDialog, QApplication
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import QTimer, Qt
from ui.editor_tab import EditorTab
from ui.widgets import DiffDialog
from ui.dialogs import VersionManagerDialog
from core.file_ops import read_file_content, write_file_content, ensure_dir, load_json, save_json, get_app_dir


RESTORE_OPENED_FILES_LIMIT = 1


class TabManagerMixin:
    """File/tab lifecycle: open, close, switch, reload, save, undo, diff, versions."""

    def _t(self, key, fallback="", **kwargs):
        """Safe translation helper for this mixin."""
        if hasattr(self, "tr_text"):
            try:
                return self.tr_text(key, **kwargs)
            except Exception:
                pass

        if kwargs and fallback:
            try:
                return fallback.format(**kwargs)
            except Exception:
                return fallback
        return fallback or key

    def current_tab(self):
        return self.tab_widget.currentWidget()

    def current_text_code(self):
        tab = self.current_tab()
        return tab.text_code if tab else None

    def close_tab(self, index):
        tab = self.tab_widget.widget(index)
        if not tab:
            return

        file_path = getattr(tab, "file_path", "")
        self.tab_widget.removeTab(index)

        if file_path:
            still_open = False
            for i in range(self.tab_widget.count()):
                other_tab = self.tab_widget.widget(i)
                if getattr(other_tab, "file_path", "") == file_path:
                    still_open = True
                    break

            if not still_open and file_path in self.file_watcher.files():
                try:
                    self.file_watcher.removePath(file_path)
                except Exception:
                    pass

            reload_timer = self._reload_timers.pop(file_path, None)
            if reload_timer:
                try:
                    reload_timer.stop()
                    reload_timer.deleteLater()
                except Exception:
                    pass
            self._pending_reload_files.discard(file_path)

        tab.deleteLater()
        self.refresh_open_files_sidebar()
        if file_path:
            self.add_operation_log(
                self._t("tab.log.closed", "文件已关闭：{file_name}", file_name=os.path.basename(file_path)),
                "info")
        self.save_settings()

    def update_recent_menu(self):
        self.recent_menu.clear()
        recent_files = self.settings.get("recent_files", [])
        if not recent_files:
            action = self.recent_menu.addAction(
                self.tr_text("menu.no_recent_files") if hasattr(self, "tr_text") else "暂无最近文件")
            action.setEnabled(False)
            return

        for file_path in recent_files:
            if os.path.exists(file_path):
                action = self.recent_menu.addAction(f"📄 {os.path.basename(file_path)}")
                action.setToolTip(file_path)
                action.triggered.connect(lambda checked, p=file_path: self.open_file_in_tab(p))

        self.recent_menu.addSeparator()
        clear_action = self.recent_menu.addAction(
            self.tr_text("menu.clear_recent_files") if hasattr(self, "tr_text") else "🧹 清空最近文件")
        clear_action.triggered.connect(self.clear_recent_files)

    def clear_recent_files(self):
        self.settings["recent_files"] = []
        self.update_recent_menu()
        self.save_settings()

    def add_to_recent(self, file_path):
        recent_files = self.settings.get("recent_files", [])
        if file_path in recent_files:
            recent_files.remove(file_path)
        recent_files.insert(0, file_path)
        self.settings["recent_files"] = recent_files[:10]
        self.update_recent_menu()
        self.save_settings()

    def restore_opened_files(self):
        self._is_restoring_files = True
        try:
            opened_files = self.settings.get("opened_files", [])
            last_active_file = self.settings.get("last_active_file", "")

            restore_candidates = []
            if last_active_file and os.path.exists(last_active_file):
                restore_candidates.append(last_active_file)

            restore_limit = max(1, int(RESTORE_OPENED_FILES_LIMIT))
            for file_path in opened_files:
                if len(restore_candidates) >= restore_limit:
                    break
                if file_path and os.path.exists(file_path) and file_path not in restore_candidates:
                    restore_candidates.append(file_path)

            for file_path in restore_candidates:
                self.open_file_in_tab(file_path, silent=True)

            if restore_candidates:
                normalized_last_active = os.path.normpath(os.path.abspath(restore_candidates[0]))
                for i in range(self.tab_widget.count()):
                    tab = self.tab_widget.widget(i)
                    tab_path = getattr(tab, "file_path", "")
                    if tab_path and os.path.normpath(os.path.abspath(tab_path)) == normalized_last_active:
                        self.tab_widget.setCurrentIndex(i)
                        break

            self.apply_active_project_filter(force=True)
            self.refresh_open_files_sidebar(force=True)
        finally:
            self._is_restoring_files = False

    def on_tab_changed(self, index):
        if getattr(self, "_is_restoring_files", False):
            return

        tab = self.current_tab()
        if tab:
            current_file_label = self._t("tab.current_file", "当前文件")
            self.update_file_path_label(f"{current_file_label}: {tab.file_path}", "#303133")
            self.add_operation_log(
                self._t("tab.log.switched", "已切换到文件：{file_name}", file_name=os.path.basename(tab.file_path)),
                "info")
        else:
            self.update_file_path_label(
                self.tr_text("status.file.none") if hasattr(self, "tr_text") else "当前未加载文件",
                "gray")

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("tab.dialog.open_file.title", "选择 Python 文件"),
            "",
            self._t("tab.dialog.file_filter", "Python Files (*.py);;All Files (*)"))
        if file_path:
            self.open_file_in_tab(file_path)

    def _path_belongs_to_root(self, file_path, root_path):
        if not file_path or not root_path:
            return False
        try:
            normalized_file = os.path.normcase(os.path.abspath(file_path))
            normalized_root = os.path.normcase(os.path.abspath(root_path))
            return normalized_file == normalized_root or normalized_file.startswith(normalized_root + os.sep)
        except Exception:
            return False

    def _sync_active_project_for_file(self, file_path):
        """打开/切换文件时，根据文件所属项目同步当前激活项目。"""
        if not file_path or not hasattr(self, "project_tree"):
            return

        try:
            roots = self.project_tree.get_project_roots()
            matched_root = ""
            for root in roots:
                if self._path_belongs_to_root(file_path, root):
                    if not matched_root or len(os.path.abspath(root)) > len(os.path.abspath(matched_root)):
                        matched_root = root

            if matched_root:
                self.project_tree.set_active_project_root(matched_root)
                self.settings["active_project_root"] = matched_root
        except Exception:
            pass

    def apply_active_project_filter(self, force=False):
        """只显示当前激活项目下的标签页。

        实现策略：
        - 不使用 QTabBar.setTabVisible / setTabEnabled，避免 Qt TabBar 滚轮和滚动按钮状态异常；
        - 非当前项目的 Tab 会临时从 QTabWidget 移出并缓存；
        - 切回对应项目时再恢复，不关闭文件、不丢编辑历史。
        """
        if not hasattr(self, "tab_widget"):
            return

        if not hasattr(self, "_hidden_project_tabs"):
            self._hidden_project_tabs = {}

        active_root = ""
        if hasattr(self, "project_tree"):
            try:
                active_root = self.project_tree.get_active_project_root()
            except Exception:
                active_root = self.settings.get("active_project_root", "")
        else:
            active_root = self.settings.get("active_project_root", "")

        active_root = os.path.normpath(os.path.abspath(active_root)) if active_root else ""

        visible_paths = []
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            file_path = getattr(tab, "file_path", "")
            if file_path:
                visible_paths.append(os.path.normpath(os.path.abspath(file_path)))

        hidden_paths = sorted(
            os.path.normpath(os.path.abspath(path))
            for path in getattr(self, "_hidden_project_tabs", {}).keys()
            if path
        )
        filter_state = (active_root, tuple(sorted(visible_paths)), tuple(hidden_paths))

        if not force and getattr(self, "_last_project_filter_state", None) == filter_state:
            return

        self._last_project_filter_state = filter_state

        # 先恢复所有缓存 Tab，再按当前项目重新过滤。
        # 这样可以避免多次切换项目后 Tab 顺序/状态越来越乱。
        hidden_items = list(self._hidden_project_tabs.values())
        self._hidden_project_tabs.clear()

        for item in hidden_items:
            widget = item.get("widget")
            if not widget:
                continue
            file_path = getattr(widget, "file_path", "")
            title = item.get("title") or os.path.basename(file_path) or self._t("tab.untitled", "未命名")
            tooltip = item.get("tooltip") or file_path
            try:
                index = self.tab_widget.addTab(widget, title)
                self.tab_widget.setTabToolTip(index, tooltip)
            except Exception:
                pass

        # 没有激活项目时显示全部。
        if not active_root:
            self.refresh_open_files_sidebar()
            return

        first_active_index = -1
        current_widget = self.tab_widget.currentWidget()

        # 从后往前移除，避免索引变化。
        for index in range(self.tab_widget.count() - 1, -1, -1):
            tab = self.tab_widget.widget(index)
            file_path = getattr(tab, "file_path", "")
            is_temporary_file = bool(getattr(tab, "is_temporary_file", False))
            belongs_to_active = self._path_belongs_to_root(file_path, active_root)

            if is_temporary_file or belongs_to_active:
                first_active_index = index
                continue

            try:
                title = self.tab_widget.tabText(index)
                tooltip = self.tab_widget.tabToolTip(index)
                self.tab_widget.removeTab(index)
                self._hidden_project_tabs[file_path] = {
                    "widget": tab,
                    "title": title,
                    "tooltip": tooltip,
                }
            except Exception:
                pass

        if current_widget and self.tab_widget.indexOf(current_widget) >= 0:
            self.tab_widget.setCurrentWidget(current_widget)
        elif first_active_index >= 0 and first_active_index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(first_active_index)
        elif self.tab_widget.count() > 0:
            self.tab_widget.setCurrentIndex(0)

        self.refresh_open_files_sidebar()

    def open_file_in_tab(self, file_path, silent=False, temporary=False):
        if not file_path:
            return

        file_path = os.path.normpath(os.path.abspath(file_path))
        is_restoring_files = getattr(self, "_is_restoring_files", False)
        if not is_restoring_files and not temporary:
            self._sync_active_project_for_file(file_path)

        if not hasattr(self, "_hidden_project_tabs"):
            self._hidden_project_tabs = {}

        hidden_item = self._hidden_project_tabs.pop(file_path, None)
        if hidden_item and hidden_item.get("widget"):
            tab = hidden_item["widget"]
            if temporary:
                setattr(tab, "is_temporary_file", True)
            title = hidden_item.get("title") or os.path.basename(file_path)
            tooltip = hidden_item.get("tooltip") or file_path
            try:
                index = self.tab_widget.addTab(tab, title)
                self.tab_widget.setTabToolTip(index, tooltip)
                self.tab_widget.setCurrentIndex(index)
                if not is_restoring_files:
                    self.apply_active_project_filter(force=True)
                    self.refresh_open_files_sidebar()
                if not silent:
                    self.add_operation_log(
                        self._t("tab.log.switched", "已切换到文件：{file_name}", file_name=os.path.basename(file_path)),
                        "info")
                return
            except Exception:
                pass

        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'file_path') and os.path.normpath(os.path.abspath(tab.file_path)) == file_path:
                if temporary:
                    setattr(tab, "is_temporary_file", True)
                self.tab_widget.setCurrentIndex(i)
                if not is_restoring_files:
                    self.apply_active_project_filter(force=temporary)
                    self.refresh_open_files_sidebar()
                if not silent:
                    self.add_operation_log(
                        self._t("tab.log.switched", "已切换到文件：{file_name}", file_name=os.path.basename(file_path)),
                        "info")
                return

        try:
            content = read_file_content(file_path)
        except Exception as e:
            if not silent:
                QMessageBox.critical(
                    self,
                    self._t("tab.error.open_failed.title", "打开失败"),
                    self._t(
                        "tab.error.open_failed.message",
                        "无法打开文件：{file_path}\n\n原因：{error}",
                        file_path=file_path,
                        error=e))
                self.add_operation_log(
                    self._t("tab.log.open_failed", "文件打开失败：{file_name}", file_name=os.path.basename(file_path)),
                    "error")
            return

        new_tab = EditorTab(file_path, content)
        setattr(new_tab, "is_temporary_file", bool(temporary))
        file_name = os.path.basename(file_path)
        index = self.tab_widget.addTab(new_tab, file_name)
        self.tab_widget.setCurrentIndex(index)

        if not is_restoring_files:
            self.add_to_recent(file_path)

        if file_path not in self.file_watcher.files():
            try:
                self.file_watcher.addPath(file_path)
            except Exception:
                pass

        if not is_restoring_files:
            self.apply_active_project_filter(force=True)
            self.refresh_open_files_sidebar()

        if not silent:
            self.add_operation_log(
                self._t("tab.log.opened", "文件已打开：{file_name}", file_name=os.path.basename(file_path)),
                "success")

    def on_file_changed(self, file_path):
        if not file_path:
            return

        timer = self._reload_timers.get(file_path)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda path=file_path: self._reload_file_from_disk(path))
            self._reload_timers[file_path] = timer

        self._pending_reload_files.add(file_path)
        timer.start(180)

    def _reload_file_from_disk(self, file_path):
        if not file_path:
            return

        if getattr(self, "_suppress_reload", False):
            self._pending_reload_files.discard(file_path)
            return

        self._pending_reload_files.discard(file_path)

        if not os.path.exists(file_path):
            return

        target_tab = None
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'file_path') and tab.file_path == file_path:
                target_tab = tab
                break

        if target_tab is None:
            if file_path in self.file_watcher.files():
                try:
                    self.file_watcher.removePath(file_path)
                except Exception:
                    pass
            return

        try:
            new_content = read_file_content(file_path)
        except Exception as e:
            print(self._t("tab.reload.failed", "自动重载失败: {error}", error=e))
            return

        try:
            if target_tab.text_code.toPlainText() != new_content:
                cursor = target_tab.text_code.textCursor()
                pos = cursor.position()

                target_tab.text_code.blockSignals(True)
                target_tab.text_code.setPlainText(new_content)
                target_tab.text_code.blockSignals(False)

                target_tab.history.append(new_content)

                cursor = target_tab.text_code.textCursor()
                cursor.setPosition(min(pos, len(new_content)))
                target_tab.text_code.setTextCursor(cursor)
        except Exception as e:
            print(self._t("tab.reload.update_failed", "更新编辑器内容失败: {error}", error=e))

        if file_path not in self.file_watcher.files():
            try:
                self.file_watcher.addPath(file_path)
            except Exception as e:
                print(self._t("tab.reload.watch_failed", "重新监听文件失败: {error}", error=e))

    def refresh_open_files_sidebar(self, force=False):
        if not hasattr(self, "project_tree"):
            return

        open_paths = set()
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if tab and hasattr(tab, "file_path"):
                try:
                    open_paths.add(os.path.normpath(os.path.abspath(tab.file_path)))
                except Exception:
                    open_paths.add(tab.file_path)

        hidden_tabs = getattr(self, "_hidden_project_tabs", {})
        for item in hidden_tabs.values():
            tab = item.get("widget") if isinstance(item, dict) else None
            if tab and hasattr(tab, "file_path"):
                try:
                    open_paths.add(os.path.normpath(os.path.abspath(tab.file_path)))
                except Exception:
                    open_paths.add(tab.file_path)

        if not force and getattr(self, "_last_open_files_sidebar_paths", None) == open_paths:
            return

        self._last_open_files_sidebar_paths = set(open_paths)
        self.project_tree.set_open_files(open_paths)

    def rebuild_project_tree(self):
        if hasattr(self, "project_tree"):
            self.project_tree.rebuild()

    def create_new_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._t("tab.dialog.new_file.title", "新建 Python 文件"),
            "",
            self._t("tab.dialog.file_filter", "Python Files (*.py);;All Files (*)"))
        if not file_path:
            return

        try:
            if not os.path.exists(file_path):
                write_file_content(file_path, "")
            self.open_file_in_tab(file_path)
        except Exception as e:
            QMessageBox.critical(
                self,
                self._t("tab.error.new_failed.title", "新建失败"),
                self._t(
                    "tab.error.new_failed.message",
                    "无法新建文件：{file_path}\n\n原因：{error}",
                    file_path=file_path,
                    error=e))

    def manual_save_current_file(self):
        tab = self.current_tab()
        if not tab:
            return
        current_code = tab.text_code.toPlainText()
        self.save_to_file(tab.file_path, current_code)
        self.update_file_path_label(
            self._t("tab.saved_file", "✅ 已保存: {file_path}", file_path=tab.file_path),
            "#67C23A")
        self.add_operation_log(
            self._t("tab.log.saved", "文件已保存：{file_name}", file_name=os.path.basename(tab.file_path)),
            "success")

    def save_to_file(self, file_path, content):
        if not file_path:
            return

        suppress_reload = getattr(self, "_suppress_reload", False)
        is_watching = file_path in self.file_watcher.files()
        if is_watching and not suppress_reload:
            try:
                self.file_watcher.removePath(file_path)
            except Exception:
                pass

        try:
            write_file_content(file_path, content)
        except Exception as e:
            QMessageBox.critical(
                self,
                self._t("tab.error.save_failed.title", "保存失败"),
                self._t(
                    "tab.error.save_failed.message",
                    "无法保存文件：{file_path}\n\n原因：{error}",
                    file_path=file_path,
                    error=e))
            return
        finally:
            if is_watching and not suppress_reload:
                try:
                    self.file_watcher.addPath(file_path)
                except Exception:
                    pass

    def save_key_version(self):
        tab = self.current_tab()
        if not tab:
            QMessageBox.warning(
                self,
                self._t("tab.warning.title", "警告"),
                self._t("tab.warning.no_open_file", "当前没有打开的文件！"))
            return

        app_dir = get_app_dir()
        backup_dir = os.path.join(app_dir, "key_versions")
        ensure_dir(backup_dir)

        original_name = os.path.basename(tab.file_path)
        name, ext = os.path.splitext(original_name)
        time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{name}_v{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)

        current_code = tab.text_code.toPlainText()
        write_file_content(backup_path, current_code)

        json_path = os.path.join(backup_dir, "versions_info.json")
        info = load_json(json_path, {})
        if tab.file_path not in info:
            info[tab.file_path] = []

        info[tab.file_path].append({"time": time_str, "filename": backup_filename})
        save_json(json_path, info)

        QMessageBox.information(
            self,
            self._t("tab.version.backup_success.title", "备份成功"),
            self._t(
                "tab.version.backup_success.message",
                "✅ 关键版本已保存至：\n{backup_path}\n\n后续如果你想找回，可以直接在管理面板中查看。",
                backup_path=backup_path))

    def manage_versions(self):
        tab = self.current_tab()
        if not tab:
            QMessageBox.warning(
                self,
                self._t("tab.notice.title", "提示"),
                self._t("tab.notice.open_file_for_versions", "请先打开一个文件，才能查看它的关联版本。"))
            return
        current_code = tab.text_code.toPlainText()
        dialog = VersionManagerDialog(tab.file_path, current_code, self)
        dialog.exec()

    def undo_change(self):
        tab = self.current_tab()
        if not tab:
            return

        if len(tab.history) > 1:
            tab.history.pop()
            previous_code = tab.history[-1]
            tab.text_code.setPlainText(previous_code)
            self.save_to_file(tab.file_path, previous_code)
            QMessageBox.information(
                self,
                self._t("tab.undo.success.title", "撤销成功"),
                self._t("tab.undo.success.message", "已恢复到上一步状态并保存。"))
        else:
            QMessageBox.information(
                self,
                self._t("tab.undo.initial.title", "提示"),
                self._t("tab.undo.initial.message", "已经是最初加载的状态，无法继续撤销。"))

    def show_diff(self):
        tab = self.current_tab()
        if not tab or not tab.history:
            return

        original_code = tab.history[0].splitlines(keepends=True)
        current_code = tab.text_code.toPlainText().splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_code,
            current_code,
            fromfile=self._t("tab.diff.from", "原始代码"),
            tofile=self._t("tab.diff.to", "当前代码"))
        diff_text = "".join(diff)

        if not diff_text:
            diff_text = self._t("tab.diff.no_change", "代码没有任何改变。")

        dialog = DiffDialog(diff_text, self)
        dialog.exec()
