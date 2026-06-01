"""AICoderApp — main application window assembling all mixins and core logic."""
import os
import json
import difflib
import time
from PySide6.QtWidgets import QMainWindow, QApplication, QMessageBox
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtCore import Qt, QFileSystemWatcher, QByteArray, QTimer
from core.replace_engine import (
    normalize_replace_block_text,
    extract_replace_blocks,
    build_replace_blocks_signature,
    ReplaceBlock,
    apply_replace_blocks,
    group_blocks_by_file,
)
from core.file_ops import get_app_dir
from app.ui_builder import UIBuilderMixin
from app.tab_manager import TabManagerMixin
from app.clipboard_feedback import ClipboardFeedbackMixin
from app.i18n import DEFAULT_LANGUAGE, normalize_language, translate


class AICoderApp(QMainWindow, UIBuilderMixin, TabManagerMixin, ClipboardFeedbackMixin):
    def __init__(self):
        super().__init__()
        self.current_language = DEFAULT_LANGUAGE
        self._sync_application_title()
        self.resize(1240, 780)
        self.setMinimumSize(680, 500)
        self.setAcceptDrops(True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self.on_file_changed)

        self.clipboard = QApplication.clipboard()
        self.clipboard_auto_enabled = False
        self.last_clipboard_text = ""
        self.last_auto_applied_text = ""
        self.last_auto_skipped_text = ""
        self.last_auto_applied_signature = ""
        self.last_auto_skipped_signature = ""
        self.last_failed_feedback_payload = None
        self.last_failed_feedback_summary = ""
        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.setInterval(800)
        self.clipboard_timer.timeout.connect(self.check_clipboard_auto_apply)
        self.clipboard_timer.start()

        self.window_flash_timer = QTimer(self)
        self.window_flash_timer.setSingleShot(True)
        self.window_flash_timer.timeout.connect(self.clear_window_flash_state)
        self._last_border_flash_key = None
        self._main_container_base_style = """
            QFrame#main_container {
                background-color: #FFFFFF;
                border: 1px solid #E8EEF7;
                border-radius: 16px;
            }
        """
        self._pending_reload_files = set()
        self._reload_timers = {}
        self._is_restoring_files = False
        self._suppress_reload = False
        self._compact_mode = None

        self._resize_layout_timer = QTimer(self)
        self._resize_layout_timer.setSingleShot(True)
        self._resize_layout_timer.setInterval(80)
        self._resize_layout_timer.timeout.connect(lambda: self.apply_responsive_layout())

        startup_t0 = time.perf_counter()

        step_t0 = time.perf_counter()
        self.load_settings()
        print(f"[startup] load_settings: {time.perf_counter() - step_t0:.3f}s")

        step_t0 = time.perf_counter()
        self.init_ui()
        print(f"[startup] init_ui: {time.perf_counter() - step_t0:.3f}s")

        step_t0 = time.perf_counter()
        self.restore_window_placement()
        print(f"[startup] restore_window_placement: {time.perf_counter() - step_t0:.3f}s")

        QTimer.singleShot(120, self._restore_opened_files_after_startup)
        QTimer.singleShot(180, lambda: self.apply_responsive_layout(force=True))

        print(f"[startup] constructor_total_without_restore: {time.perf_counter() - startup_t0:.3f}s")

    def _restore_opened_files_after_startup(self):
        """窗口先显示，再恢复上次打开的文件，避免启动白屏等待。"""
        try:
            step_t0 = time.perf_counter() if "time" in globals() else None
            self.restore_opened_files()
            if step_t0 is not None:
                print(f"[startup] restore_opened_files_async: {time.perf_counter() - step_t0:.3f}s")
        except Exception as exc:
            try:
                self.add_operation_log(
                    self.tr_text("main.log.restore_opened_failed", error=exc),
                    "warning")
            except Exception:
                pass

    def load_settings(self):
        app_dir = get_app_dir()
        self.settings_path = os.path.join(app_dir, "settings.json")
        self.settings = {
            "recent_files": [],
            "opened_files": [],
            "window_geometry": "",
            "window_state": "",
            "clipboard_auto_enabled": False,
            "last_active_file": "",
            "splitter_sizes": [620, 340],
            "sidebar_splitter_sizes": [170, 940],
            "project_roots": [],
            "active_project_root": "",
            "language": DEFAULT_LANGUAGE,
        }
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                if isinstance(saved_settings, dict):
                    self.settings.update(saved_settings)
            except Exception:
                pass

        self.current_language = normalize_language(self.settings.get("language", DEFAULT_LANGUAGE))
        self.settings["language"] = self.current_language
        self._sync_application_title()

    def tr_text(self, key, **kwargs):
        return translate(key, getattr(self, "current_language", DEFAULT_LANGUAGE), **kwargs)

    def _sync_application_title(self):
        """同步窗口标题和 Qt 应用名，避免标题栏、任务栏、系统菜单显示旧品牌名。"""
        title = self.tr_text("app.title")
        self.setWindowTitle(title)

        app = QApplication.instance()
        if app is not None:
            app.setApplicationName(title)
            app.setApplicationDisplayName(title)

    def set_language(self, language):
        language = normalize_language(language)
        if language == getattr(self, "current_language", DEFAULT_LANGUAGE):
            return

        self.current_language = language
        self.settings["language"] = language
        self.save_settings()

        self._sync_application_title()

        if hasattr(self, "retranslate_ui"):
            self.retranslate_ui()

        if hasattr(self, "apply_responsive_layout"):
            self.apply_responsive_layout(force=True)

    def restore_window_placement(self):
        """恢复上次窗口大小、位置和窗口状态。"""
        try:
            geometry = self.settings.get("window_geometry", "")
            if isinstance(geometry, str) and geometry:
                geometry_data = QByteArray.fromBase64(geometry.encode("utf-8"))
                if not geometry_data.isEmpty():
                    self.restoreGeometry(geometry_data)

            state = self.settings.get("window_state", "")
            if isinstance(state, str) and state:
                state_data = QByteArray.fromBase64(state.encode("utf-8"))
                if not state_data.isEmpty():
                    self.restoreState(state_data)
        except Exception as e:
            try:
                self.add_operation_log(
                    self.tr_text("main.log.restore_window_failed", error=e),
                    "warning")
            except Exception:
                pass

    def save_settings(self):
        opened_files = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'file_path'):
                opened_files.append(tab.file_path)

        hidden_tabs = getattr(self, "_hidden_project_tabs", {})
        for item in hidden_tabs.values():
            tab = item.get("widget") if isinstance(item, dict) else None
            if tab and hasattr(tab, "file_path") and tab.file_path not in opened_files:
                opened_files.append(tab.file_path)

        self.settings["opened_files"] = opened_files

        current_tab = self.current_tab()
        self.settings["last_active_file"] = (
            current_tab.file_path if current_tab and hasattr(current_tab, 'file_path') else "")

        if hasattr(self, "splitter"):
            try:
                self.settings["splitter_sizes"] = self.splitter.sizes()
            except Exception:
                pass

        if hasattr(self, "body_splitter"):
            try:
                self.settings["sidebar_splitter_sizes"] = self.body_splitter.sizes()
            except Exception:
                pass

        if hasattr(self, "project_tree"):
            try:
                self.settings["active_project_root"] = self.project_tree.get_active_project_root()
            except Exception:
                pass

        self.settings["window_geometry"] = self.saveGeometry().toBase64().data().decode("utf-8")
        self.settings["window_state"] = self.saveState().toBase64().data().decode("utf-8")

        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def enter_floating_mode(self):
        """切换到迷你悬浮模式，节省屏幕占用。"""
        if not hasattr(self, "floating_status_widget"):
            return

        try:
            geo = self.geometry()
            x = geo.right() - self.floating_status_widget.width() - 24
            y = geo.top() + 36
            self.floating_status_widget.move(max(0, x), max(0, y))
        except Exception:
            pass

        self.floating_status_widget.update_status(self.tr_text("main.float.entered"), "info")
        self.floating_status_widget.show()
        self.hide()

    def exit_floating_mode(self):
        """从迷你悬浮模式恢复完整主界面。"""
        if hasattr(self, "floating_status_widget"):
            self.floating_status_widget.hide()

        self.show()
        self.raise_()
        self.activateWindow()
        if hasattr(self, "apply_responsive_layout"):
            self.apply_responsive_layout(force=True)

    def closeEvent(self, event):
        try:
            if hasattr(self, "clipboard_timer"):
                self.clipboard_timer.stop()
            if hasattr(self, "window_flash_timer"):
                self.window_flash_timer.stop()
            if hasattr(self, "_preview_debounce_timer"):
                try:
                    self._preview_debounce_timer.stop()
                except Exception:
                    pass
            if hasattr(self, "_sidebar_splitter_save_timer"):
                try:
                    self._sidebar_splitter_save_timer.stop()
                except Exception:
                    pass
            if hasattr(self, "_resize_layout_timer"):
                try:
                    self._resize_layout_timer.stop()
                except Exception:
                    pass
            if hasattr(self, "_reload_timers"):
                for timer in self._reload_timers.values():
                    try:
                        timer.stop()
                    except Exception:
                        pass
                self._reload_timers.clear()
            if hasattr(self, "floating_status_widget"):
                try:
                    self.floating_status_widget.hide()
                    self.floating_status_widget.deleteLater()
                except Exception:
                    pass
        except Exception:
            pass

        self.save_settings()
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and (os.path.isdir(path) or os.path.isfile(path)):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and (os.path.isdir(path) or os.path.isfile(path)):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        accepted = False
        for url in event.mimeData().urls():
            path = os.path.normpath(url.toLocalFile())
            if not path:
                continue

            if os.path.isdir(path):
                self._handle_drop_resource_folder(path)
                accepted = True
            elif os.path.isfile(path):
                self._handle_drop_resource_file(path)
                accepted = True

        if accepted:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_drop_resource_file(self, file_path):
        """拖入单个文件：只临时打开，不自动添加项目、不要求 main.py。"""
        if not file_path:
            return False

        file_path = os.path.normpath(os.path.abspath(file_path))
        if not os.path.isfile(file_path):
            return False

        self.open_file_in_tab(file_path, temporary=True)
        self.add_operation_log(
            self.tr_text("main.log.temp_file_opened", file_name=os.path.basename(file_path)),
            "success")
        return True

    def _handle_drop_resource_folder(self, folder_path):
        """拖入文件夹：直接加入左侧项目目录，不检查 main.py。"""
        if not folder_path:
            return False

        folder_path = os.path.normpath(os.path.abspath(folder_path))
        if not os.path.isdir(folder_path):
            return False

        added = self.add_project_root_if_missing(folder_path)
        self.settings["active_project_root"] = folder_path

        self.refresh_project_roots_ui()
        if hasattr(self, "project_tree") and hasattr(self.project_tree, "set_active_project_root"):
            self.project_tree.set_active_project_root(folder_path, emit_signal=True)

        if hasattr(self, "apply_active_project_filter"):
            self.apply_active_project_filter(force=True)

        self.save_settings()

        project_name = os.path.basename(folder_path) or folder_path
        if added:
            self.add_operation_log(
                self.tr_text("main.log.project_added_by_drop", project_name=project_name),
                "success")
        else:
            self.add_operation_log(
                self.tr_text("main.log.project_switched_existing", project_name=project_name),
                "info")

        return True

    def detect_project_root_from_python_file(self, file_path):
        """
        从拖入的 Python 文件自动推断项目根目录。

        策略：
        1. 从文件所在目录向上查找常见入口文件；
        2. 优先使用包含 main.py / app.py / manage.py 等入口文件的目录；
        3. 如果没有找到入口文件，则退回到当前文件所在目录。
        """
        if not file_path:
            return ""

        current_dir = os.path.abspath(os.path.dirname(file_path))
        entry_files = {"main.py", "app.py", "manage.py", "run.py", "__main__.py"}

        candidate = current_dir
        last_valid_dir = current_dir

        while candidate and os.path.isdir(candidate):
            try:
                names = set(os.listdir(candidate))
            except Exception:
                break

            if names.intersection(entry_files):
                return os.path.normpath(candidate)

            parent = os.path.dirname(candidate)
            if parent == candidate:
                break

            last_valid_dir = candidate
            candidate = parent

        return os.path.normpath(last_valid_dir)

    def add_project_root_if_missing(self, project_root):
        """把自动识别出的项目根目录加入设置，已存在则跳过。"""
        if not project_root:
            return False

        project_root = os.path.normpath(os.path.abspath(project_root))
        roots = self.settings.setdefault("project_roots", [])
        normalized_roots = {os.path.normpath(os.path.abspath(root)) for root in roots if root}

        if project_root in normalized_roots:
            return False

        roots.append(project_root)
        return True

    def refresh_project_roots_ui(self):
        """
        刷新左侧项目目录。

        优先同步 settings["project_roots"] 到 ProjectTreeWidget，
        避免只保存配置但左侧树不立即更新。
        """
        if not hasattr(self, "project_tree"):
            return False

        try:
            roots = self.settings.get("project_roots", [])
            if roots:
                self.project_tree.set_project_roots(roots)
            elif hasattr(self.project_tree, "rebuild"):
                self.project_tree.rebuild()

            active_root = self.settings.get("active_project_root", "")
            if active_root and hasattr(self.project_tree, "set_active_project_root"):
                self.project_tree.set_active_project_root(active_root)

            self.refresh_open_files_sidebar()
            if hasattr(self, "apply_active_project_filter"):
                self.apply_active_project_filter()
            return True
        except Exception as exc:
            self.add_operation_log(
                self.tr_text("main.log.refresh_project_failed", error=exc),
                "warning")
            return False

    def resizeEvent(self, event):
        super().resizeEvent(event)

        tab = self.current_tab()
        if tab:
            self.update_file_path_label(
                f"{self.tr_text('tab.current_file')}: {tab.file_path}",
                "#303133")
        else:
            self.update_file_path_label(self.tr_text("status.file.none"), "gray")

        if hasattr(self, "_resize_layout_timer"):
            self._resize_layout_timer.start()
        else:
            self.apply_responsive_layout()

    # ================= search and copy =================

    def smart_select_block(self):
        text_code = self.current_text_code()
        if not text_code:
            return

        cursor = text_code.textCursor()
        if not cursor.hasSelection():
            return

        text = text_code.toPlainText()
        lines = text.split('\n')

        pos = cursor.selectionStart()
        current_line_idx = text[:pos].count('\n')

        start_line_idx = -1
        target_indent = -1

        for i in range(current_line_idx, -1, -1):
            line = lines[i]
            stripped = line.lstrip()
            if stripped.startswith("def ") or stripped.startswith("class "):
                start_line_idx = i
                target_indent = len(line) - len(stripped)
                break

        if start_line_idx == -1:
            return

        while start_line_idx > 0:
            prev_line = lines[start_line_idx - 1].lstrip()
            if prev_line.startswith("@"):
                start_line_idx -= 1
            else:
                break

        end_line_idx = start_line_idx
        for i in range(start_line_idx + 1, len(lines)):
            line = lines[i]
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                end_line_idx = i
                continue
            current_indent = len(line) - len(stripped)
            if current_indent <= target_indent:
                break
            end_line_idx = i

        start_pos = sum(len(lines[i]) + 1 for i in range(start_line_idx))
        end_pos = sum(len(lines[i]) + 1 for i in range(end_line_idx + 1)) - 1

        new_cursor = text_code.textCursor()
        new_cursor.setPosition(start_pos)
        new_cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
        text_code.setTextCursor(new_cursor)

    def find_next(self):
        text_code = self.current_text_code()
        if not text_code:
            return
        query = self.search_input.text()
        if query:
            found = text_code.find(query)
            if not found:
                cursor = text_code.textCursor()
                cursor.movePosition(QTextCursor.Start)
                text_code.setTextCursor(cursor)
                if text_code.find(query):
                    self.smart_select_block()
                else:
                    QMessageBox.information(
                        self,
                        self.tr_text("search.dialog.title"),
                        self.tr_text("search.not_found"))
            else:
                self.smart_select_block()

    def find_prev(self):
        text_code = self.current_text_code()
        if not text_code:
            return
        query = self.search_input.text()
        if query:
            options = QTextDocument.FindBackward
            found = text_code.find(query, options)
            if not found:
                cursor = text_code.textCursor()
                cursor.movePosition(QTextCursor.End)
                text_code.setTextCursor(cursor)
                if text_code.find(query, options):
                    self.smart_select_block()
            else:
                self.smart_select_block()

    def copy_selected(self):
        text_code = self.current_text_code()
        if not text_code:
            return
        cursor = text_code.textCursor()
        if cursor.hasSelection():
            selected_text = (
                cursor.selectedText()
                .replace("\u2029", "\n")
                .replace("\u2028", "\n")
            )
            QApplication.clipboard().setText(selected_text)
            QMessageBox.information(
                self,
                self.tr_text("copy.dialog.copied.title"),
                self.tr_text("copy.selected.success"))
        else:
            QMessageBox.warning(
                self,
                self.tr_text("tab.notice.title"),
                self.tr_text("copy.selected.empty"))

    def copy_all(self):
        text_code = self.current_text_code()
        if not text_code:
            return
        all_text = text_code.toPlainText()
        if all_text.strip():
            QApplication.clipboard().setText(all_text)
            QMessageBox.information(
                self,
                self.tr_text("copy.all.title"),
                self.tr_text("copy.all.success"))
        else:
            QMessageBox.warning(
                self,
                self.tr_text("tab.notice.title"),
                self.tr_text("copy.all.empty"))

    def _get_active_project_root_for_context(self):
        """获取当前要复制结构的项目根目录，优先使用左侧激活项目。"""
        active_root = ""
        if hasattr(self, "project_tree"):
            try:
                active_root = self.project_tree.get_active_project_root()
            except Exception:
                active_root = ""

        if not active_root:
            active_root = self.settings.get("active_project_root", "")

        if not active_root and hasattr(self, "project_tree"):
            try:
                roots = self.project_tree.get_project_roots()
                active_root = roots[0] if roots else ""
            except Exception:
                active_root = ""

        if not active_root:
            roots = self.settings.get("project_roots", [])
            active_root = roots[0] if roots else ""

        if not active_root:
            return ""

        active_root = os.path.normpath(os.path.abspath(active_root))
        return active_root if os.path.isdir(active_root) else ""


    def _build_project_tree_text(self, root_path, max_depth=5, max_entries=650):
        """生成适合发给 AI 的轻量项目结构文本，带深度和数量兜底。"""
        if not root_path or not os.path.isdir(root_path):
            return "", False

        excluded_dirs = {
            "__pycache__", ".git", ".svn", ".hg", "node_modules",
            ".venv", "venv", "env", ".claude", ".idea", ".vscode",
            "key_versions", "dist", "build", ".cache", ".pytest_cache",
            ".mypy_cache", ".ruff_cache", "htmlcov", "coverage",
            "python", "lib", "libs", "dlls", "scripts", "site-packages",
        }
        allowed_exts = {
            ".py", ".pyw",
        }
        always_include_files = set()

        root_name = os.path.basename(root_path) or root_path
        lines = [f"{root_name}/"]
        entry_count = 0
        truncated = False

        def should_include_file(name):
            if name in always_include_files:
                return True
            return os.path.splitext(name)[1].lower() in allowed_exts

        def collect_visible_entries(current_dir, depth=0):
            """只收集 Python 文件，以及包含 Python 文件的目录。"""
            if depth >= max_depth:
                return []

            try:
                names = sorted(
                    os.listdir(current_dir),
                    key=lambda item: (not os.path.isdir(os.path.join(current_dir, item)), item.lower())
                )
            except Exception:
                return []

            visible_entries = []
            for name in names:
                if name.startswith("."):
                    continue

                full_path = os.path.join(current_dir, name)
                if os.path.isdir(full_path):
                    if name.lower() in excluded_dirs:
                        continue

                    child_entries = collect_visible_entries(full_path, depth + 1)
                    if child_entries:
                        visible_entries.append((name, full_path, True, child_entries))
                elif should_include_file(name):
                    visible_entries.append((name, full_path, False, None))

            return visible_entries

        def render_entries(entries, prefix=""):
            nonlocal entry_count, truncated

            if truncated:
                return

            for index, (name, full_path, is_dir, child_entries) in enumerate(entries):
                if entry_count >= max_entries:
                    lines.append(self.tr_text("project.tree.omitted", prefix=prefix))
                    truncated = True
                    return

                is_last = index == len(entries) - 1
                connector = "└─ " if is_last else "├─ "
                suffix = "/" if is_dir else ""
                lines.append(f"{prefix}{connector}{name}{suffix}")
                entry_count += 1

                if is_dir and child_entries:
                    child_prefix = prefix + ("   " if is_last else "│  ")
                    render_entries(child_entries, child_prefix)

        render_entries(collect_visible_entries(root_path))
        return "\n".join(lines), truncated

    def build_project_structure_context_text(self):
        """构建复制给聊天 AI 的项目结构上下文。"""
        project_root = self._get_active_project_root_for_context()
        if not project_root:
            return ""

        tree_text, truncated = self._build_project_tree_text(project_root)

        truncate_hint = self.tr_text("project.tree.truncated") if truncated else ""

        return self.tr_text(
            "project.context.prompt",
            project_root=project_root,
            truncate_hint=truncate_hint,
            tree_text=tree_text)

    def copy_project_structure(self):
        """复制当前激活项目结构给 AI。"""
        context_text = self.build_project_structure_context_text()
        if not context_text.strip():
            QMessageBox.warning(
                self,
                self.tr_text("tab.notice.title"),
                self.tr_text("project.copy.no_project"))
            return

        QApplication.clipboard().setText(context_text)
        self.add_operation_log(self.tr_text("project.copy.log.success"), "success")
        QMessageBox.information(
            self,
            self.tr_text("project.copy.success.title"),
            self.tr_text("project.copy.success.message")
        )

    # ================= AI change application =================

    def _find_or_open_tab(self, file_path, silent=False):
        """Find an existing tab for file_path, or open it. Returns EditorTab or None."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'file_path') and tab.file_path == file_path:
                return tab

        if not os.path.exists(file_path):
            if not silent:
                QMessageBox.warning(
                    self,
                    self.tr_text("tab.warning.title"),
                    self.tr_text("apply.warning.file_not_exists", file_path=file_path))
            return None

        self.open_file_in_tab(file_path, silent=True)
        # Find the tab we just opened
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'file_path') and tab.file_path == file_path:
                return tab
        return None

    def _apply_to_single_file(self, tab, blocks, silent, require_unique_match, return_details):
        """Apply blocks to a single tab. Writes back to editor and saves."""
        current_code = tab.text_code.toPlainText()
        new_code, result = apply_replace_blocks(current_code, blocks, require_unique_match)

        if result["success_count"] > 0:
            tab.text_code.setPlainText(new_code)
            tab.history.append(new_code)
            self.save_to_file(tab.file_path, new_code)

            first_new_code = blocks[0].new_code.strip().split('\n')[0]
            if first_new_code:
                cursor = tab.text_code.textCursor()
                cursor.setPosition(0)
                tab.text_code.setTextCursor(cursor)
                tab.text_code.find(first_new_code)

        result["reason"] = "ok" if result["success"] else "replace_failed"
        return result

    def _aggregate_results(self, all_results, original_tab, silent, return_details):
        """Aggregate multi-file results and show appropriate message."""
        total_success = sum(r.get("success_count", 0) for r in all_results)
        total_fail = sum(r.get("fail_count", 0) for r in all_results)
        total_replaced = sum(r.get("total_replaced_occurrences", 0) for r in all_results)

        all_failed_blocks = []
        all_diagnostics = []
        multi_match = False
        zero_match = False
        unique_fail = False

        for r in all_results:
            all_failed_blocks.extend(r.get("failed_blocks", []))

            file_path = r.get("file", "")
            for diagnostic in r.get("diagnostics", []):
                if isinstance(diagnostic, dict):
                    item = dict(diagnostic)
                    item.setdefault("file", file_path)
                    all_diagnostics.append(item)

            if r.get("multi_match_failed"):
                multi_match = True
            if r.get("zero_match_failed"):
                zero_match = True
            if r.get("unique_match_failed"):
                unique_fail = True

        has_any_success = total_success > 0
        has_any_fail = total_fail > 0

        if has_any_success and not silent:
            file_summaries = []
            for r in all_results:
                fname = os.path.basename(r.get("file", ""))
                sc = r.get("success_count", 0)
                fc = r.get("fail_count", 0)
                if sc > 0 or fc > 0:
                    file_summaries.append(
                        self.tr_text(
                            "apply.dialog.file_summary",
                            file_name=fname,
                            success_count=sc,
                            fail_count=fc))
            QMessageBox.information(
                self,
                self.tr_text("apply.dialog.done.title"),
                self.tr_text(
                    "apply.dialog.done.message",
                    success_count=total_success,
                    replace_count=total_replaced,
                    file_summaries="\n".join(file_summaries)))

        if has_any_fail and not silent:
            if silent and require_unique_match and unique_fail:
                pass  # silent mode skips warning for unique match failures
            elif not silent:
                QMessageBox.warning(
                    self,
                    self.tr_text("apply.dialog.partial_failed.title"),
                    self.tr_text(
                        "apply.dialog.partial_failed.message",
                        success_count=total_success,
                        fail_count=total_fail,
                        failed_details="\n".join(all_failed_blocks)))

        if has_any_success and not silent:
            self.text_ai_input.clear()
            self.clear_failed_feedback()
            self.add_operation_log(
                self.tr_text(
                    "apply.log.success_multi",
                    block_count=total_success,
                    file_count=len(all_results)),
                "success")

        result = {
            "success": has_any_success and not has_any_fail,
            "reason": ("ok" if not has_any_fail
                       else ("unique_match_failed" if unique_fail
                             else ("partial_failed" if has_any_success
                                   else "replace_failed"))),
            "success_count": total_success,
            "fail_count": total_fail,
            "total_replaced_occurrences": total_replaced,
            "failed_blocks": all_failed_blocks,
            "diagnostics": all_diagnostics,
            "multi_match_failed": multi_match,
            "zero_match_failed": zero_match,
            "unique_match_failed": unique_fail,
            "files": all_results,
        }
        return result if return_details else (has_any_success and not has_any_fail)

    def apply_ai_changes(self, silent=False, content_override=None,
                         require_unique_match=False, return_details=False,
                         selected_blocks=None):
        tab = self.current_tab()
        if not tab:
            if not silent:
                QMessageBox.warning(
                    self,
                    self.tr_text("tab.warning.title"),
                    self.tr_text("apply.warning.load_file_first"))
            return {"success": False, "reason": "no_tab"} if return_details else False

        ai_content = content_override if content_override is not None else self.text_ai_input.toPlainText()

        if selected_blocks is not None:
            blocks = list(selected_blocks)
        else:
            ai_content = normalize_replace_block_text(ai_content)
            blocks = extract_replace_blocks(ai_content)

        if not blocks:
            result = {"success": False, "reason": "invalid_block"}
            if not silent:
                QMessageBox.critical(
                    self,
                    self.tr_text("apply.error.invalid_block.title"),
                    self.tr_text("apply.error.invalid_block.message"))
                if hasattr(self, "cache_failed_feedback"):
                    self.cache_failed_feedback("invalid_block", ai_content, result)
            return result if return_details else False

        current_file = tab.file_path if tab else ""
        active_project_root = ""
        if hasattr(self, "project_tree"):
            try:
                active_project_root = self.project_tree.get_active_project_root()
            except Exception:
                active_project_root = self.settings.get("active_project_root", "")

        all_project_roots = self.settings.get("project_roots", [])
        project_roots = (
            [active_project_root] + [root for root in all_project_roots if root != active_project_root]
            if active_project_root else all_project_roots
        )
        groups = group_blocks_by_file(blocks, current_file, project_roots=project_roots)

        # Single file (current tab) — fast path
        if len(groups) == 1 and list(groups.keys())[0] == os.path.normpath(current_file):
            result = self._apply_to_single_file(tab, blocks, silent, require_unique_match, True)
            result.setdefault("file", current_file)

            if result["success"] and silent:
                self.tab_widget.setCurrentWidget(tab)

            if result["success"] and not silent:
                self.text_ai_input.clear()
                self.clear_failed_feedback()
                self.add_operation_log(
                    self.tr_text("apply.log.success_single", block_count=result["success_count"]),
                    "success")
            elif not result["success"] and not silent and hasattr(self, "cache_failed_feedback"):
                self.cache_failed_feedback(result.get("reason", "replace_failed"), ai_content, result)
                self.add_operation_log(self.tr_text("apply.log.manual_failed_feedback_ready"), "warning")

            return result if return_details else result["success"]

        # Multi-file routing
        original_index = self.tab_widget.currentIndex()
        self._suppress_reload = True
        all_results = []
        focus_success_tab_index = None

        try:
            for file_path, file_blocks in groups.items():
                target_tab = self._find_or_open_tab(file_path, silent)
                if not target_tab:
                    all_results.append({
                        "file": file_path, "success": False, "reason": "open_failed",
                        "success_count": 0, "fail_count": len(file_blocks),
                        "total_replaced_occurrences": 0,
                        "failed_blocks": [
                            self.tr_text("apply.open_failed.block", file_path=file_path)
                        ],
                        "diagnostics": [{
                            "file": file_path,
                            "type": "open_failed",
                            "match_count": 0,
                            "old_preview": "",
                            "suggestion": self.tr_text("apply.open_failed.suggestion"),
                        }],
                        "multi_match_failed": False, "zero_match_failed": False,
                        "unique_match_failed": False,
                    })
                    continue

                result = self._apply_to_single_file(
                    target_tab, file_blocks, silent, require_unique_match, True)
                result["file"] = file_path
                all_results.append(result)

                if silent and result.get("success_count", 0) > 0:
                    for index in range(self.tab_widget.count()):
                        tab_item = self.tab_widget.widget(index)
                        if getattr(tab_item, "file_path", "") == file_path:
                            focus_success_tab_index = index
                            break
        finally:
            self._suppress_reload = False
            if silent and focus_success_tab_index is not None and focus_success_tab_index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(focus_success_tab_index)
            elif original_index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(original_index)

        aggregate_result = self._aggregate_results(all_results, tab, silent, True)

        if not aggregate_result.get("success") and not silent and hasattr(self, "cache_failed_feedback"):
            self.cache_failed_feedback(
                aggregate_result.get("reason", "replace_failed"),
                ai_content,
                aggregate_result
            )
            self.add_operation_log(self.tr_text("apply.log.manual_failed_feedback_ready"), "warning")

        return aggregate_result if return_details else aggregate_result.get("success", False)

    def _on_preview_apply(self, selected_only):
        if selected_only:
            blocks = self.preview_panel.get_enabled_blocks()
            if not blocks:
                QMessageBox.information(
                    self,
                    self.tr_text("tab.notice.title"),
                    self.tr_text("preview.no_selected_blocks"))
                return
            self.apply_ai_changes(selected_blocks=blocks)
        else:
            self.apply_ai_changes()
