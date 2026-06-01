"""Reusable custom widgets: QuickActionButton, DiffDialog, PreviewPanel, ProjectTree."""
import os
from PySide6.QtWidgets import (QPushButton, QDialog, QVBoxLayout, QHBoxLayout,
                               QTextEdit, QSizePolicy, QFrame, QCheckBox,
                               QLabel, QTreeWidget, QTreeWidgetItem, QHeaderView,
                               QScrollArea, QWidget, QMenu)
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRect, QSize, Signal, QFileSystemWatcher, QTimer, QSettings, QPoint
from app.i18n import DEFAULT_LANGUAGE, translate

def _widget_tr(widget, key, fallback="", **kwargs):
    """Resolve translation from nearest parent that provides tr_text; fallback to app i18n."""
    parent = widget
    while parent is not None:
        if hasattr(parent, "tr_text"):
            try:
                return parent.tr_text(key, **kwargs)
            except Exception:
                break
        parent = parent.parent() if hasattr(parent, "parent") else None

    language = DEFAULT_LANGUAGE
    app_parent = widget.parent() if hasattr(widget, "parent") else None
    if app_parent is not None:
        language = getattr(app_parent, "current_language", DEFAULT_LANGUAGE)

    text = translate(key, language, **kwargs)
    if text == key and fallback:
        if kwargs:
            try:
                return fallback.format(**kwargs)
            except Exception:
                return fallback
        return fallback
    return text


class DiffDialog(QDialog):
    def __init__(self, diff_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_widget_tr(self, "widgets.diff.title", "代码修改对比 (Diff)"))
        self.resize(750, 500)
        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)

        html_diff = ("<pre style='font-family: Consolas, \"Courier New\", monospace; "
                     "font-size: 14px; line-height: 1.5;'>")
        for line in diff_text.splitlines():
            safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            if line.startswith('+') and not line.startswith('+++'):
                html_diff += f"<div style='color: #24292f; background-color: #e6ffec;'>{safe_line}</div>"
            elif line.startswith('-') and not line.startswith('---'):
                html_diff += f"<div style='color: #24292f; background-color: #ffebe9;'>{safe_line}</div>"
            elif line.startswith('@@'):
                html_diff += f"<div style='color: #0969da; background-color: #ddf4ff;'>{safe_line}</div>"
            else:
                html_diff += f"<div>{safe_line}</div>"
        html_diff += "</pre>"

        text_edit.setHtml(html_diff)
        layout.addWidget(text_edit)


class QuickActionButton(QPushButton):
    def __init__(self, icon_text, title, subtitle="", compact_title=None, danger=False, parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.title_text = title
        self.subtitle_text = subtitle
        self.compact_title = compact_title or title
        self.danger = danger
        self.compact_mode = False
        self.setText("")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(64)
        self.setMaximumHeight(72)

    def set_action_content(self, icon_text, title, subtitle="", compact_title=None):
        self.icon_text = icon_text
        self.title_text = title
        self.subtitle_text = subtitle
        self.compact_title = compact_title or title
        self.update()

    def set_compact_mode(self, compact):
        self.compact_mode = bool(compact)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                min-height: 0px;
            }
        """)
        if self.compact_mode:
            self.setMinimumSize(48, 40)
            self.setMaximumHeight(42)
        else:
            self.setMinimumSize(64, 64)
            self.setMaximumHeight(72)
        self.updateGeometry()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        enabled = self.isEnabled()
        hovered = self.underMouse() and enabled

        if not enabled:
            bg = QColor("#F8FAFC")
            border = QColor("#E2E8F0")
            title_color = QColor("#CBD5E1")
            subtitle_color = QColor("#CBD5E1")
            icon_color = QColor("#CBD5E1")
        elif self.danger:
            bg = QColor("#FEF2F2") if hovered else QColor("#FBFDFF")
            border = QColor("#FECACA") if hovered else QColor("#E5ECF6")
            title_color = QColor("#DC2626") if hovered else QColor("#EF4444")
            subtitle_color = QColor("#EF4444")
            icon_color = QColor("#EF4444")
        else:
            bg = QColor("#F8FBFF") if hovered else QColor("#FBFDFF")
            border = QColor("#BFDBFE") if hovered else QColor("#E5ECF6")
            title_color = QColor("#2563EB") if hovered else QColor("#334155")
            subtitle_color = QColor("#64748B")
            icon_color = QColor("#2563EB")

        painter.setPen(border)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 10, 10)

        if self.compact_mode:
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(title_color)
            text_rect = rect.adjusted(6, 0, -6, 0)
            compact_text = f"{self.icon_text}  {self.compact_title}"
            compact_text = QFontMetrics(font).elidedText(compact_text, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignCenter, compact_text)
            return

        icon_rect = QRect(rect.left() + 14, rect.top() + 18, 22, 22)
        title_rect = QRect(rect.left() + 42, rect.top() + 13, rect.width() - 54, 20)
        subtitle_rect = QRect(rect.left() + 42, rect.top() + 36, rect.width() - 54, 20)

        icon_font = painter.font()
        icon_font.setPointSize(12)
        icon_font.setBold(True)
        painter.setFont(icon_font)
        painter.setPen(icon_color)
        painter.drawText(icon_rect, Qt.AlignCenter, self.icon_text)

        title_font = painter.font()
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(title_color)
        title_text = QFontMetrics(title_font).elidedText(self.title_text, Qt.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, title_text)

        subtitle_font = painter.font()
        subtitle_font.setPointSize(9)
        subtitle_font.setBold(True)
        painter.setFont(subtitle_font)
        painter.setPen(subtitle_color)
        subtitle_text = QFontMetrics(subtitle_font).elidedText(self.subtitle_text, Qt.ElideRight, subtitle_rect.width())
        painter.drawText(subtitle_rect, Qt.AlignLeft | Qt.AlignVCenter, subtitle_text)


class PreviewBlockWidget(QFrame):
    """Single replace block preview row: checkbox + file + old→new summary."""

    toggled = Signal()

    def __init__(self, block, block_index, parent=None):
        super().__init__(parent)
        self.block = block
        self.block_index = block_index
        self.setObjectName("preview_block")
        self.setStyleSheet("""
            QFrame#preview_block {
                background-color: #FBFDFF;
                border: 1px solid #E5ECF6;
                border-radius: 8px;
                margin: 1px 0;
            }
            QFrame#preview_block:hover { background-color: #F8FBFF; }
        """)
        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.toggled.connect(self.toggled.emit)
        top_row.addWidget(self.checkbox)

        file_name = os.path.basename(block.target_file) if block.target_file else _widget_tr(
            self, "widgets.preview.current_tab", "(当前标签页)")
        file_label = QLabel(f"📄  {file_name}")
        file_label.setStyleSheet("color: #2563EB; font-size: 11px; font-weight: 800;")
        file_label.setToolTip(block.target_file or _widget_tr(
            self, "widgets.preview.current_tab.tooltip", "当前标签页"))
        top_row.addWidget(file_label)
        top_row.addStretch()

        block_num = QLabel(_widget_tr(
            self, "widgets.preview.block_index", "第 {index} 个", index=block_index + 1))
        block_num.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 600;")
        top_row.addWidget(block_num)

        main_layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        bottom_row.setContentsMargins(22, 0, 0, 0)

        old_preview = block.old_code.strip()[:60].replace('\n', ' ↵ ')
        new_preview = block.new_code.strip()[:60].replace('\n', ' ↵ ') if block.new_code.strip() else _widget_tr(
            self, "widgets.preview.delete", "(删除)")

        old_lbl = QLabel(old_preview)
        old_lbl.setStyleSheet(
            "color: #DC2626; font-size: 10px; font-family: Consolas, monospace; "
            "background: #FEF2F2; border-radius: 3px; padding: 1px 4px;")
        old_lbl.setToolTip(block.old_code.strip())
        old_lbl.setTextFormat(Qt.PlainText)
        bottom_row.addWidget(old_lbl, 1)

        arrow = QLabel("→")
        arrow.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: 800;")
        arrow.setFixedWidth(16)
        arrow.setAlignment(Qt.AlignCenter)
        bottom_row.addWidget(arrow)

        new_color = "#16A34A" if block.new_code.strip() else "#F59E0B"
        new_bg = "#F0FDF4" if block.new_code.strip() else "#FFF7ED"
        new_lbl = QLabel(new_preview)
        new_lbl.setStyleSheet(
            f"color: {new_color}; font-size: 10px; font-family: Consolas, monospace; "
            f"background: {new_bg}; border-radius: 3px; padding: 1px 4px;")
        new_lbl.setToolTip(block.new_code.strip() or _widget_tr(
            self, "widgets.preview.delete", "(删除)"))
        new_lbl.setTextFormat(Qt.PlainText)
        bottom_row.addWidget(new_lbl, 1)

        main_layout.addLayout(bottom_row)

    def is_checked(self):
        return self.checkbox.isChecked()


class PreviewPanel(QFrame):
    """Collapsible preview panel showing parsed replace blocks before applying."""

    apply_requested = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("preview_panel")
        self.setStyleSheet("""
            QFrame#preview_panel {
                background-color: #FFFFFF;
                border: 1px solid #E8EEF7;
                border-radius: 12px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        self.header_btn = QPushButton()
        self.header_btn.setStyleSheet(
            "text-align: left; padding: 4px 6px; font-weight: 800; font-size: 11px; "
            "color: #334155; border: none; background: transparent;")
        self.header_btn.clicked.connect(self._toggle_collapse)
        layout.addWidget(self.header_btn)

        self.blocks_container = QWidget()
        self.blocks_layout = QVBoxLayout(self.blocks_container)
        self.blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_layout.setSpacing(3)
        layout.addWidget(self.blocks_container)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_apply_selected = QPushButton(_widget_tr(
            self, "widgets.preview.apply_selected", "应用选中"))
        self.btn_apply_selected.setStyleSheet(
            "background: #3B82F6; color: white; border: none; border-radius: 6px; "
            "padding: 5px 10px; font-size: 11px; font-weight: 800;")
        self.btn_apply_selected.clicked.connect(lambda: self.apply_requested.emit(True))

        self.btn_apply_all = QPushButton(_widget_tr(
            self, "widgets.preview.apply_all_count", "应用全部（{count}）", count=0))
        self.btn_apply_all.setStyleSheet(
            "background: #22C55E; color: white; border: none; border-radius: 6px; "
            "padding: 5px 10px; font-size: 11px; font-weight: 800;")
        self.btn_apply_all.clicked.connect(lambda: self.apply_requested.emit(False))

        btn_row.addWidget(self.btn_apply_selected)
        btn_row.addWidget(self.btn_apply_all)
        layout.addLayout(btn_row)

        self._collapsed = False
        self._block_widgets = []

    def populate(self, blocks):
        for w in self._block_widgets:
            w.setParent(None)
            w.deleteLater()
        self._block_widgets.clear()

        for i, block in enumerate(blocks):
            pw = PreviewBlockWidget(block, i, self)
            pw.toggled.connect(self._update_button_labels)
            self.blocks_layout.addWidget(pw)
            self._block_widgets.append(pw)

        self._update_button_labels()
        self.setVisible(len(blocks) > 0)

    def _update_button_labels(self):
        enabled = self.get_enabled_count()
        total = len(self._block_widgets)
        self.btn_apply_selected.setText(
            _widget_tr(self, "widgets.preview.apply_selected_count", "应用选中（{count}）", count=enabled)
            if enabled
            else _widget_tr(self, "widgets.preview.apply_selected", "应用选中")
        )
        self.btn_apply_all.setText(
            _widget_tr(self, "widgets.preview.apply_all_count", "应用全部（{count}）", count=total)
        )
        self.header_btn.setText(
            _widget_tr(self, "widgets.preview.header.expanded", "▼  预览替换块（{count} 个）", count=total)
            if not self._collapsed
            else _widget_tr(self, "widgets.preview.header.collapsed", "▶  预览替换块（{count} 个）", count=total)
        )

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.blocks_container.setVisible(not self._collapsed)
        self.btn_apply_selected.setVisible(not self._collapsed)
        self.btn_apply_all.setVisible(not self._collapsed)
        self._update_button_labels()
        if self._collapsed:
            self.setFixedHeight(36)
        else:
            self.setMinimumHeight(60)
            self.setMaximumHeight(16777215)

    def get_enabled_count(self):
        return sum(1 for w in self._block_widgets if w.is_checked())

    def get_enabled_blocks(self):
        return [w.block for w in self._block_widgets if w.is_checked()]

    def clear(self):
        for w in self._block_widgets:
            w.setParent(None)
            w.deleteLater()
        self._block_widgets.clear()
        self.setVisible(False)


class DropResourceZone(QFrame):
    """Sidebar drop zone: drop code files to open temporarily, folders to add as projects."""

    file_dropped = Signal(str)
    folder_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop_resource_zone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(52)
        self.setMaximumHeight(72)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(2)

        self.title_label = QLabel(_widget_tr(
            self, "widgets.drop.title", "📥 拖入代码 / 文件夹"))
        self.title_label.setAcceptDrops(False)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            "color: #16A34A; font-size: 11px; font-weight: 900; "
            "background: transparent; border: none;")

        self.hint_label = QLabel(_widget_tr(
            self, "widgets.drop.hint", "文件临时打开 · 文件夹加入项目"))
        self.hint_label.setAcceptDrops(False)
        self.hint_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(
            "color: #64748B; font-size: 10px; font-weight: 600; "
            "background: transparent; border: none;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.hint_label)

        self._compact = False
        self._apply_style(active=False)

    def _apply_style(self, active=False):
        border_color = "#22C55E" if active else "#86EFAC"
        bg_color = "#F0FDF4" if active else "#FBFFFC"
        self.setStyleSheet(f"""
            QFrame#drop_resource_zone {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 10px;
            }}
        """)

    def set_compact_mode(self, compact):
        self._compact = bool(compact)
        if self._compact:
            self.title_label.setText("📥")
            self.hint_label.setVisible(False)
            self.setMinimumHeight(44)
            self.setMaximumHeight(52)
        else:
            self.title_label.setText(_widget_tr(
                self, "widgets.drop.title", "📥 拖入代码 / 文件夹"))
            self.hint_label.setText(_widget_tr(
                self, "widgets.drop.hint", "文件临时打开 · 文件夹加入项目"))
            self.hint_label.setVisible(True)
            self.setMinimumHeight(52)
            self.setMaximumHeight(72)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if self._is_supported_path(path):
                    self._apply_style(active=True)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if self._is_supported_path(path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._apply_style(active=False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._apply_style(active=False)

        if not event.mimeData().hasUrls():
            event.ignore()
            return

        accepted = False
        for url in event.mimeData().urls():
            path = os.path.normpath(url.toLocalFile())
            if not path:
                continue

            if os.path.isdir(path):
                self.folder_dropped.emit(path)
                accepted = True
            elif os.path.isfile(path):
                self.file_dropped.emit(path)
                accepted = True

        if accepted:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _is_supported_path(self, path):
        if not path:
            return False
        if os.path.isdir(path):
            return True
        return os.path.isfile(path)


class FloatingStatusWidget(QFrame):
    """Mini floating status window. Double-click to restore the main window."""

    restore_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("floating_status_widget")
        self.setWindowFlags(
            Qt.Tool |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        # 顶层悬浮窗必须启用透明背景，否则内部 border-radius 生效后，
        # 窗口本身的矩形底板仍会露出来，看起来就是“直角背景”。
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setAcceptDrops(False)
        self.setFixedSize(260, 86)

        self._level = "info"
        self._marquee_index = 0
        self._drag_pos = None
        self._border_color = QColor("#3B82F6")
        self._background_color = QColor("#EFF6FF")
        self._border_width = 2
        self._base_robot_text = "🤖"
        self._base_title_text = _widget_tr(self, "widgets.float.title", "AI 助手悬浮中")
        # 成功反馈不持续播放：每次 success 只入队一次“机器人摆动”。
        # direction: -1 表示先往左，1 表示先往右；每次成功后交替。
        self._robot_feedback_direction = -1
        self._robot_feedback_steps_remaining = 0
        self._robot_feedback_current_alignment = Qt.AlignCenter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(3)
        title_row.addStretch()

        self.robot_label = QLabel(self._base_robot_text)
        self.robot_label.setFixedWidth(28)
        self.robot_label.setAlignment(Qt.AlignCenter)
        self.robot_label.setStyleSheet(
            "color: #0F172A; font-size: 13px; font-weight: 900; "
            "background: transparent; border: none;"
        )

        self.title_label = QLabel(self._base_title_text)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setStyleSheet(
            "color: #0F172A; font-size: 13px; font-weight: 900; "
            "background: transparent; border: none;"
        )

        title_row.addWidget(self.robot_label)
        title_row.addWidget(self.title_label)
        title_row.addStretch()

        self.status_label = QLabel(_widget_tr(self, "widgets.float.restore", "双击恢复主界面"))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #475569; font-size: 11px; font-weight: 700; "
            "background: transparent; border: none;"
        )

        layout.addLayout(title_row)
        layout.addWidget(self.status_label)

        self._marquee_timer = QTimer(self)
        self._marquee_timer.setInterval(180)
        self._marquee_timer.timeout.connect(self._tick_marquee)
        self._marquee_timer.start()

        self.update_status(_widget_tr(
            self, "widgets.float.entered", "悬浮模式已开启，双击恢复主界面"), "info")
        QTimer.singleShot(0, self._restore_saved_position)

    def update_status(self, text, level="info"):
        if not text:
            text = _widget_tr(self, "widgets.float.default_status", "等待操作反馈...")
        self._level = level or "info"
        self._marquee_index = 0
        self.status_label.setText(text)
        self.status_label.setToolTip(text)

        if self._level == "success":
            self._queue_success_robot_feedback()
        elif self._level not in {"warning", "error"}:
            self._robot_feedback_steps_remaining = 0
            self._robot_feedback_current_alignment = Qt.AlignCenter

        self._update_title_feedback()
        self._apply_style()

    def _tick_marquee(self):
        self._marquee_index = (self._marquee_index + 1) % 8

        if self._robot_feedback_steps_remaining > 0:
            if self._robot_feedback_steps_remaining % 2 == 0:
                self._robot_feedback_current_alignment = (
                    Qt.AlignLeft | Qt.AlignVCenter
                    if self._robot_feedback_direction < 0
                    else Qt.AlignRight | Qt.AlignVCenter
                )
            else:
                self._robot_feedback_current_alignment = Qt.AlignCenter

            self._robot_feedback_steps_remaining -= 1

            if self._robot_feedback_steps_remaining <= 0:
                self._robot_feedback_current_alignment = Qt.AlignCenter

        self._update_title_feedback()
        self._apply_style()

    def _queue_success_robot_feedback(self):
        # 每次成功应用，追加一次“偏移 -> 回中”的两帧动作。
        # 如果短时间连续成功 3 次，这里会累计成 3 次动作，不会被后一次覆盖。
        self._robot_feedback_steps_remaining += 2
        self._robot_feedback_direction *= -1

    def _update_title_feedback(self):
        self.title_label.setText(self._base_title_text)

        if self._level == "success":
            self.robot_label.setText("🤖")
            self.robot_label.setAlignment(self._robot_feedback_current_alignment)
            return

        if self._level == "warning":
            self.robot_label.setText("⚠️")
            self.robot_label.setAlignment(Qt.AlignCenter)
            return

        if self._level == "error":
            self.robot_label.setText("🚨")
            self.robot_label.setAlignment(Qt.AlignCenter)
            return

        self.robot_label.setText(self._base_robot_text)
        self.robot_label.setAlignment(Qt.AlignCenter)

    def _apply_style(self):
        palette = {
            "info": ("#3B82F6", "#EFF6FF"),
            "success": ("#22C55E", "#F0FDF4"),
            "warning": ("#F59E0B", "#FFFBEB"),
            "error": ("#EF4444", "#FEF2F2"),
            "neutral": ("#94A3B8", "#F8FAFC"),
        }
        color, bg = palette.get(self._level, palette["info"])

        border_width = 2
        if self._level in {"warning", "error"}:
            border_width = 2 + (self._marquee_index % 3)
        elif self._level == "success" and self._robot_feedback_steps_remaining > 0:
            border_width = 2 + (self._marquee_index % 2)

        self._border_color = QColor(color)
        self._background_color = QColor(bg)
        self._border_width = border_width
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        inset = max(1, self._border_width)
        rect = self.rect().adjusted(inset, inset, -inset, -inset)

        pen = self._border_color
        pen.setAlpha(255)

        painter.setPen(pen)
        painter.setBrush(self._background_color)
        painter.drawRoundedRect(rect, 16, 16)

        super().paintEvent(event)

    def _position_settings(self):
        return QSettings("AIHelper", "FloatingStatusWidget")

    def _restore_saved_position(self):
        settings = self._position_settings()
        x = settings.value("x", None)
        y = settings.value("y", None)

        if x is None or y is None:
            return

        try:
            point = QPoint(int(x), int(y))
        except (TypeError, ValueError):
            return

        screen = self.screen()
        if screen:
            available = screen.availableGeometry()
            max_x = available.right() - self.width()
            max_y = available.bottom() - self.height()
            safe_x = min(max(point.x(), available.left()), max_x)
            safe_y = min(max(point.y(), available.top()), max_y)
            point = QPoint(safe_x, safe_y)

        self.move(point)

    def _save_current_position(self):
        try:
            settings = self._position_settings()
            pos = self.pos()
            settings.setValue("x", pos.x())
            settings.setValue("y", pos.y())
            settings.sync()
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._save_current_position()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._save_current_position()
            self.restore_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # 悬浮框可能是 hide/show 复用，不一定每次重新创建；
        # 因此每次重新显示时都恢复一次上次保存的位置。
        QTimer.singleShot(0, self._restore_saved_position)

    def hideEvent(self, event):
        # 双击恢复主界面通常会 hide 悬浮框，这里也保存一次，确保再次悬浮还能回到当前位置。
        self._save_current_position()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._save_current_position()
        super().closeEvent(event)


class ProjectTreeWidget(QWidget):
    """Directory tree showing project files, with open-file highlighting.
    Supports multiple project roots, each as a collapsible top-level node."""

    file_double_clicked = Signal(str)
    project_remove_requested = Signal(str)
    project_selected = Signal(str)

    def __init__(self, project_roots=None, parent=None):
        super().__init__(parent)
        if project_roots is None:
            project_roots = []
        self._project_roots = [os.path.normpath(r) for r in project_roots if r and os.path.isdir(os.path.normpath(r))]
        self._active_project_root = self._project_roots[0] if self._project_roots else ""
        self._root_items = []
        self._open_files = set()
        self._all_items = []
        self._keyword = ""
        self._watched_dirs = set()
        self._max_watch_dirs = 260
        self._is_rebuilding = False

        self._dir_watcher = QFileSystemWatcher(self)
        self._dir_watcher.directoryChanged.connect(self._schedule_rebuild_for_fs_change)

        self._fs_rebuild_timer = QTimer(self)
        self._fs_rebuild_timer.setSingleShot(True)
        self._fs_rebuild_timer.setInterval(350)
        self._fs_rebuild_timer.timeout.connect(self._rebuild_after_fs_change)

        self.name_filters = {'.py', '.pyw'}
        self.excluded_dirs = {'__pycache__', '.git', '.svn', '.hg', 'node_modules',
                              '.venv', 'venv', 'env', '.claude', '.idea', '.vscode',
                              'key_versions', 'dist', 'build', '.cache', '.pytest_cache',
                              '.mypy_cache', '.ruff_cache', 'htmlcov', 'coverage',
                              'python', 'lib', 'libs', 'dlls', 'scripts', 'site-packages'}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: transparent;
                border: none;
                outline: none;
                font-size: 11px;
                color: #475569;
            }
            QTreeWidget::item {
                padding: 3px 2px;
                border-radius: 6px;
                min-height: 24px;
            }
            QTreeWidget::item:hover { background-color: #F1F5F9; color: #2563EB; }
            QTreeWidget::item:selected { background-color: #ECFDF5; color: #16A34A; font-weight: 800; }
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        QTimer.singleShot(80, self.rebuild)

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return

        path = item.data(0, Qt.UserRole)
        if not path or os.path.isfile(path):
            return

        # Only project root items (direct children of the invisible root) get the remove action.
        if item.parent() is not None:
            return

        menu = QMenu(self)
        remove_action = menu.addAction(_widget_tr(
            self,
            "widgets.project.remove",
            "🗑 移除项目「{project_name}」",
            project_name=os.path.basename(path)))
        action = menu.exec(self.tree.mapToGlobal(pos))
        if action == remove_action:
            self.project_remove_requested.emit(path)

    def rebuild(self):
        if self._is_rebuilding:
            return

        self._is_rebuilding = True
        try:
            self._reset_directory_watcher()
            self.tree.clear()
            self._all_items.clear()
            self._root_items.clear()

            if not self._project_roots:
                self._active_project_root = ""
                self.tree.addTopLevelItem(QTreeWidgetItem([
                    _widget_tr(self, "widgets.project.empty", "无项目目录 — 点击顶部按钮添加")
                ]))
                return

            for root_path in self._project_roots:
                if not os.path.isdir(root_path):
                    continue

                root_item = QTreeWidgetItem([f"📂  {os.path.basename(root_path)}"])
                root_item.setData(0, Qt.UserRole, root_path)
                root_item.setToolTip(0, root_path)

                self._walk_dir(root_path, root_item, depth=0)

                self.tree.addTopLevelItem(root_item)
                self._root_items.append(root_item)
                root_item.setExpanded(False)

            if self._active_project_root not in self._project_roots:
                self._active_project_root = self._project_roots[0] if self._project_roots else ""

            self._restyle_items()
        finally:
            self._is_rebuilding = False

    def set_project_roots(self, roots):
        self._project_roots = [os.path.normpath(r) for r in roots if r and os.path.isdir(os.path.normpath(r))]
        if self._active_project_root not in self._project_roots:
            self._active_project_root = self._project_roots[0] if self._project_roots else ""
        QTimer.singleShot(80, self.rebuild)
        if self._keyword:
            self.filter_by_keyword(self._keyword)

    def get_project_roots(self):
        return list(self._project_roots)

    def get_active_project_root(self):
        return self._active_project_root

    def set_active_project_root(self, root_path, emit_signal=False):
        root_path = os.path.normpath(root_path) if root_path else ""
        if root_path and root_path not in self._project_roots:
            return False

        if self._active_project_root == root_path:
            self._restyle_items()
            return True

        self._active_project_root = root_path
        self._restyle_items()

        if emit_signal and root_path:
            self.project_selected.emit(root_path)
        return True

    def _reset_directory_watcher(self):
        """重建项目目录监听，确保外部新增/删除文件后左侧树能自动刷新。"""
        if not hasattr(self, "_dir_watcher"):
            return

        try:
            watched_dirs = self._dir_watcher.directories()
            if watched_dirs:
                self._dir_watcher.removePaths(watched_dirs)
        except Exception:
            pass

        self._watched_dirs = set()

    def _watch_directory(self, dir_path):
        """监听目录变化；带数量上限，避免大型项目监听过多目录导致系统资源异常。"""
        if not dir_path or not os.path.isdir(dir_path):
            return

        if len(self._watched_dirs) >= self._max_watch_dirs:
            return

        normalized = os.path.normpath(os.path.abspath(dir_path))
        if normalized in self._watched_dirs:
            return

        try:
            self._dir_watcher.addPath(normalized)
            self._watched_dirs.add(normalized)
        except Exception:
            pass

    def _is_parent_suppressing_reload(self):
        parent = self.parent()
        while parent:
            if getattr(parent, "_suppress_reload", False):
                return True
            parent = parent.parent()
        return False

    def _schedule_rebuild_for_fs_change(self, changed_path):
        """文件系统变化防抖刷新。"""
        if self._is_parent_suppressing_reload():
            return
        if hasattr(self, "_fs_rebuild_timer"):
            self._fs_rebuild_timer.start()

    def _capture_expanded_paths(self):
        expanded = set()

        def visit(item):
            path = item.data(0, Qt.UserRole)
            if path and item.isExpanded():
                expanded.add(os.path.normpath(path))
            for index in range(item.childCount()):
                visit(item.child(index))

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index))
        return expanded

    def _restore_expanded_paths(self, expanded):
        if not expanded:
            return

        def visit(item):
            path = item.data(0, Qt.UserRole)
            if path and os.path.normpath(path) in expanded:
                item.setExpanded(True)
            for index in range(item.childCount()):
                visit(item.child(index))

        for index in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(index))

    def _rebuild_after_fs_change(self):
        """外部新增、删除、重命名文件后刷新项目树，并尽量保留展开状态和搜索条件。"""
        if self._is_parent_suppressing_reload():
            return

        active_root = self._active_project_root
        keyword = self._keyword
        expanded = self._capture_expanded_paths()

        self.rebuild()

        if active_root:
            self.set_active_project_root(active_root)

        self._restore_expanded_paths(expanded)

        if keyword:
            self.filter_by_keyword(keyword)

    def _walk_dir(self, dir_path, parent_item, depth):
        if depth > 5:
            return

        self._watch_directory(dir_path)

        try:
            entries = sorted(os.listdir(dir_path),
                             key=lambda e: (not os.path.isdir(os.path.join(dir_path, e)), e.lower()))
        except PermissionError:
            return

        for name in entries:
            if name.startswith('.') and name not in ('.env', '.gitignore'):
                continue
            full_path = os.path.normpath(os.path.join(dir_path, name))
            if os.path.isdir(full_path):
                if name.lower() in self.excluded_dirs:
                    continue
                dir_item = QTreeWidgetItem([f"📁  {name}"])
                dir_item.setData(0, Qt.UserRole, full_path)
                parent_item.addChild(dir_item)
                self._walk_dir(full_path, dir_item, depth + 1)
            else:
                ext = os.path.splitext(name)[1].lower()
                if ext not in self.name_filters:
                    continue
                icon = "🐍" if ext == '.py' else "📄"
                file_item = QTreeWidgetItem([f"{icon}  {name}"])
                file_item.setData(0, Qt.UserRole, full_path)
                file_item.setToolTip(0, full_path)
                parent_item.addChild(file_item)
                self._all_items.append(file_item)

    def _restyle_items(self):
        active_root_font = QFont()
        active_root_font.setBold(True)

        normal_root_font = QFont()
        normal_root_font.setBold(True)

        file_open_font = QFont()
        file_open_font.setBold(True)

        for root_item in self._root_items:
            root_path = root_item.data(0, Qt.UserRole)
            root_name = os.path.basename(root_path) or root_path
            if root_path == self._active_project_root:
                root_item.setText(0, f"🟢  {root_name}")
                root_item.setForeground(0, QColor("#16A34A"))
                root_item.setBackground(0, QColor("#ECFDF5"))
                root_item.setFont(0, active_root_font)
            else:
                root_item.setText(0, f"📂  {root_name}")
                root_item.setForeground(0, QColor("#475569"))
                root_item.setBackground(0, QColor("#FFFFFF"))
                root_item.setFont(0, normal_root_font)

        for item in self._all_items:
            path = item.data(0, Qt.UserRole)
            normalized_path = os.path.normpath(os.path.abspath(path)) if path else ""
            if normalized_path in self._open_files:
                item.setText(0, f"✅  {os.path.basename(path)}")
                item.setForeground(0, QColor("#16A34A"))
                item.setBackground(0, QColor("#FFFFFF"))
                item.setFont(0, file_open_font)
            else:
                ext = os.path.splitext(path or "")[1].lower()
                icon = "🐍" if ext == '.py' else "📄"
                item.setText(0, f"{icon}  {os.path.basename(path)}")
                item.setForeground(0, QColor("#475569"))
                item.setBackground(0, QColor("#FFFFFF"))
                item.setFont(0, QFont())

    def set_open_files(self, paths):
        normalized_paths = {
            os.path.normpath(os.path.abspath(path))
            for path in (paths or [])
            if path
        }
        if normalized_paths == self._open_files:
            return

        self._open_files = normalized_paths
        self._restyle_items()

    def set_compact_mode(self, compact):
        self.tree.setIndentation(8 if compact else 14)
        font_size = "10px" if compact else "11px"
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: transparent; border: none; outline: none;
                font-size: {font_size}; color: #475569;
            }}
            QTreeWidget::item {{
                padding: 2px 2px; border-radius: 5px; min-height: 20px;
            }}
            QTreeWidget::item:hover {{ background-color: #F1F5F9; color: #2563EB; }}
            QTreeWidget::item:selected {{ background-color: #ECFDF5; color: #16A34A; font-weight: 800; }}
        """)

    def filter_by_keyword(self, keyword):
        self._keyword = keyword.strip().lower() if keyword else ""
        for item in self._all_items:
            path = (item.data(0, Qt.UserRole) or "").lower()
            name = os.path.basename(path) if path else ""
            if not self._keyword:
                item.setHidden(False)
            else:
                item.setHidden(self._keyword not in name and self._keyword not in path)

        for i in range(self.tree.topLevelItemCount()):
            self._show_if_children_visible(self.tree.topLevelItem(i))

    def _show_if_children_visible(self, item):
        any_visible = False
        for ci in range(item.childCount()):
            child = item.child(ci)
            if not child.isHidden():
                any_visible = True
            self._show_if_children_visible(child)
        if not any_visible and item.childCount() > 0:
            item.setHidden(True)
        else:
            item.setHidden(False)

    def _on_item_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        if not path:
            return

        selected_root = ""
        if os.path.isdir(path) and item.parent() is None:
            selected_root = path
        else:
            selected_root = self._find_root_for_path(path)

        if selected_root:
            self.set_active_project_root(selected_root, emit_signal=True)

    def _find_root_for_path(self, path):
        if not path:
            return ""

        try:
            normalized_path = os.path.normcase(os.path.abspath(path))
            matched_root = ""
            for root in self._project_roots:
                normalized_root = os.path.normcase(os.path.abspath(root))
                if normalized_path == normalized_root or normalized_path.startswith(normalized_root + os.sep):
                    if len(normalized_root) > len(os.path.normcase(os.path.abspath(matched_root))) if matched_root else True:
                        matched_root = root
            return matched_root
        except Exception:
            return ""

    def _on_item_double_clicked(self, item, column):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            root = self._find_root_for_path(path)
            if root:
                self.set_active_project_root(root, emit_signal=True)
            self.file_double_clicked.emit(path)
