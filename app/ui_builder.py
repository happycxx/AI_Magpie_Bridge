"""UIBuilderMixin — constructs the main window UI and handles responsive layout."""
import os
import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTextEdit, QLabel, QSplitter, QMenu, QTabWidget,
                               QListWidget, QFrame, QSizePolicy, QLineEdit,
                               QGraphicsDropShadowEffect, QFileDialog, QMessageBox)
from PySide6.QtGui import QShortcut, QKeySequence, QFontMetrics, QColor
from PySide6.QtCore import Qt, QSize, QByteArray, QTimer
from ui.widgets import QuickActionButton, PreviewPanel, ProjectTreeWidget, DropResourceZone, FloatingStatusWidget
from core.replace_engine import extract_replace_blocks
from app.i18n import get_available_languages


class UIBuilderMixin:
    """Responsible for building the complete UI and adapting to window size."""

    def init_ui(self):
        # --- top toolbar ---
        top_frame = QFrame()
        top_frame.setObjectName("top_frame")

        # 顶部工具区拆成两行，避免窗口缩小时所有按钮和状态文字硬挤在一行。
        top_outer_layout = QVBoxLayout(top_frame)
        top_outer_layout.setContentsMargins(8, 8, 8, 8)
        top_outer_layout.setSpacing(6)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        top_status_layout = QHBoxLayout()
        top_status_layout.setContentsMargins(0, 0, 0, 0)
        top_status_layout.setSpacing(6)

        self.btn_load = QPushButton(self.tr_text("button.load"))
        self.btn_load.clicked.connect(self.load_file)

        self.btn_save_file = QPushButton(self.tr_text("button.save"))
        self.btn_save_file.setToolTip(self.tr_text("button.save.tooltip"))
        self.btn_save_file.clicked.connect(self.manual_save_current_file)

        self.btn_more = QPushButton(self.tr_text("button.more"))
        self.btn_more.setObjectName("btn_more")
        self.btn_more.setToolTip(self.tr_text("menu.more.tooltip"))
        self.btn_more_menu = QMenu(self)
        self.recent_menu = QMenu(self.tr_text("menu.recent_files"), self)
        self.update_recent_menu()
        self.action_save_version = self.btn_more_menu.addAction(self.tr_text("menu.save_version"))
        self.action_save_version.triggered.connect(self.save_key_version)
        self.action_manage_versions = self.btn_more_menu.addAction(self.tr_text("menu.manage_versions"))
        self.action_manage_versions.triggered.connect(self.manage_versions)
        self.btn_more_menu.addSeparator()
        self.btn_more_menu.addMenu(self.recent_menu)

        self.language_menu = QMenu(self.tr_text("menu.language"), self)
        self.language_actions = {}
        self._rebuild_language_menu()
        self.btn_more_menu.addMenu(self.language_menu)

        self.btn_more.setMenu(self.btn_more_menu)
        self.btn_more.setMinimumWidth(72)

        self.btn_auto_clipboard = QPushButton(self.tr_text("button.auto_clipboard.off"))
        self.btn_auto_clipboard.setCheckable(True)
        self.btn_auto_clipboard.setChecked(False)
        self.btn_auto_clipboard.clicked.connect(self.toggle_clipboard_auto_apply)

        self.btn_float_mode = QPushButton(self.tr_text("button.float"))
        self.btn_float_mode.setToolTip(self.tr_text("button.float.tooltip"))
        self.btn_float_mode.clicked.connect(self.enter_floating_mode)

        self.lbl_auto_status = QLabel(self.tr_text("status.auto.closed"))
        self.lbl_auto_status.setStyleSheet(
            "color: #909399; font-size: 12px; padding: 2px 6px; "
            "background: #F4F4F5; border-radius: 6px;")
        self.lbl_auto_status.setMinimumWidth(72)
        self.lbl_auto_status.setMaximumWidth(150)
        self.lbl_auto_status.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.lbl_file_path = QLabel(self.tr_text("status.file.none"))
        self.lbl_file_path.setStyleSheet("color: #909399; font-size: 12px;")
        self.lbl_file_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl_file_path.setMinimumWidth(120)
        self.lbl_file_path.setMaximumHeight(28)

        for btn in [self.btn_load, self.btn_save_file, self.btn_more, self.btn_auto_clipboard, self.btn_float_mode]:
            btn.setMinimumHeight(42)
            btn.setMaximumHeight(42)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.btn_load.setMinimumWidth(78)
        self.btn_save_file.setMinimumWidth(78)
        self.btn_more.setMinimumWidth(78)
        self.btn_auto_clipboard.setMinimumWidth(112)
        self.btn_float_mode.setMinimumWidth(76)

        top_layout.addWidget(self.btn_load)
        top_layout.addWidget(self.btn_save_file)
        top_layout.addWidget(self.btn_more)
        top_layout.addWidget(self.btn_auto_clipboard)
        top_layout.addWidget(self.btn_float_mode)
        top_layout.addStretch(1)

        top_status_layout.addWidget(self.lbl_auto_status)
        top_status_layout.addWidget(self.lbl_file_path, 1)

        top_outer_layout.addLayout(top_layout)
        top_outer_layout.addLayout(top_status_layout)

        # --- main splitter (left code + right AI panel) ---
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # ===== left: code area =====
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 14, 0)
        search_layout.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr_text("search.placeholder"))
        self.search_input.returnPressed.connect(self.find_next)

        self.btn_find_prev = QPushButton(self.tr_text("find.prev"))
        self.btn_find_prev.clicked.connect(self.find_prev)
        self.btn_find_next = QPushButton(self.tr_text("find.next"))
        self.btn_find_next.clicked.connect(self.find_next)

        self.btn_copy_sel = QPushButton(self.tr_text("copy.selected"))
        self.btn_copy_sel.setObjectName("btn_copy_sel")
        self.btn_copy_sel.setToolTip(self.tr_text("copy.selected.tooltip"))
        self.btn_copy_sel.clicked.connect(self.copy_selected)

        self.btn_copy_all = QPushButton(self.tr_text("copy.all"))
        self.btn_copy_all.setObjectName("btn_copy_all")
        self.btn_copy_all.setToolTip(self.tr_text("copy.all.tooltip"))
        self.btn_copy_all.clicked.connect(self.copy_all)

        self.btn_copy_project_structure = QPushButton(self.tr_text("copy.project_structure"))
        self.btn_copy_project_structure.setObjectName("btn_copy_project_structure")
        self.btn_copy_project_structure.setToolTip(self.tr_text("copy.project_structure.tooltip"))
        self.btn_copy_project_structure.clicked.connect(self.copy_project_structure)

        for btn in [self.btn_find_prev, self.btn_find_next, self.btn_copy_sel,
                    self.btn_copy_all, self.btn_copy_project_structure]:
            btn.setMinimumHeight(42)
            btn.setMaximumHeight(42)

        self.search_input.setMinimumWidth(52)
        self.search_input.setMaximumWidth(220)
        self.search_input.setMinimumHeight(42)
        self.search_input.setMaximumHeight(42)
        self.search_input.setToolTip(self.tr_text("search.tooltip"))
        shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_find.activated.connect(self.search_input.setFocus)
        shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        shortcut_save.activated.connect(self.manual_save_current_file)

        self.search_icon_label = QLabel("🔍")
        self.search_icon_label.setFixedWidth(22)
        self.search_icon_label.setAlignment(Qt.AlignCenter)

        search_layout.addWidget(self.search_icon_label)
        search_layout.addWidget(self.search_input, 0)
        search_layout.addWidget(self.btn_find_prev)
        search_layout.addWidget(self.btn_find_next)
        search_layout.addWidget(self.btn_copy_sel)
        search_layout.addWidget(self.btn_copy_all)
        search_layout.addWidget(self.btn_copy_project_structure)
        search_layout.addStretch(1)

        left_layout.addLayout(search_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                padding: 8px 15px; background: #E4E7ED;
                border: 1px solid #DCDFE6; border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF; font-weight: bold; color: #409EFF;
            }
        """)
        left_layout.addWidget(self.tab_widget)

        # ===== right: AI panel =====
        self.right_widget = QFrame()
        self.right_widget.setObjectName("ai_panel")
        self.right_widget.setMinimumWidth(220)
        self.right_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.right_widget.setStyleSheet("""
            QFrame#ai_panel {
                background-color: #FFFFFF;
                border: 1px solid #E8EEF7;
                border-radius: 14px;
            }
            QLabel#ai_panel_title {
                color: #0F172A; font-size: 13px; font-weight: 900;
                background: transparent; border: none;
            }
            QLabel#ai_panel_subtitle {
                color: #94A3B8; font-size: 11px; font-weight: 600;
                background: transparent; border: none;
            }
            QTextEdit#ai_drop_zone {
                background-color: #FBFFFC;
                border: 2px dashed #86EFAC;
                border-radius: 14px; padding: 18px;
                color: #334155;
                font-family: Consolas, "Courier New", monospace;
                font-size: 13px;
            }
            QTextEdit#ai_drop_zone:focus {
                border: 2px dashed #22C55E;
                background-color: #FFFFFF;
            }
            QFrame#ai_card {
                background-color: #FFFFFF;
                border: 1px solid #E8EEF7;
                border-radius: 14px;
            }
            QLabel#ai_card_title {
                color: #334155; font-size: 12px; font-weight: 900;
                background: transparent; border: none;
            }
            QListWidget#operation_log_list {
                background-color: transparent; border: none;
                padding: 2px; outline: none;
            }
            QListWidget#operation_log_list::item {
                color: #64748B; font-size: 11px;
                padding: 4px 2px; border-radius: 6px;
            }
            QListWidget#operation_log_list::item:selected {
                background-color: #F0FDF4; color: #16A34A;
            }
            QPushButton#quick_action_btn {
                background-color: transparent; border: none;
                padding: 0px; margin: 0px; min-height: 0px;
            }
        """)

        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setContentsMargins(12, 12, 12, 12)
        self.right_layout.setSpacing(12)

        ai_header_layout = QVBoxLayout()
        ai_header_layout.setContentsMargins(0, 0, 0, 0)
        ai_header_layout.setSpacing(3)

        self.ai_title = QLabel(self.tr_text("ai.title"))
        self.ai_title.setObjectName("ai_panel_title")
        ai_header_layout.addWidget(self.ai_title)

        self.ai_subtitle = QLabel(self.tr_text("ai.subtitle"))
        self.ai_subtitle.setObjectName("ai_panel_subtitle")
        self.ai_subtitle.setWordWrap(True)
        ai_header_layout.addWidget(self.ai_subtitle)

        self.right_layout.addLayout(ai_header_layout)

        self.text_ai_input = QTextEdit()
        self.text_ai_input.setObjectName("ai_drop_zone")
        self.text_ai_input.setMinimumHeight(110)
        self.text_ai_input.setPlaceholderText(self.tr_text("ai.placeholder"))
        self.text_ai_input.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text_ai_input.customContextMenuRequested.connect(
            lambda pos: self._paste_ai_input_from_context_menu())
        self.right_layout.addWidget(self.text_ai_input, 0)

        # Preview panel (hidden until valid replace blocks are pasted)
        self.preview_panel = PreviewPanel()
        self.preview_panel.setVisible(False)
        self.preview_panel.apply_requested.connect(self._on_preview_apply)
        self.right_layout.addWidget(self.preview_panel)

        # Debounce timer: parse blocks from text_ai_input for preview
        self._preview_debounce_timer = QTimer(self)
        self._preview_debounce_timer.setSingleShot(True)
        self._preview_debounce_timer.setInterval(400)
        self._preview_debounce_timer.timeout.connect(self._parse_and_preview)
        self.text_ai_input.textChanged.connect(
            lambda: self._preview_debounce_timer.start())

        # Operation log
        self.log_card = QFrame()
        self.log_card.setObjectName("ai_card")
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(10, 9, 10, 9)
        log_layout.setSpacing(6)
        self.log_title = QLabel(self.tr_text("log.title"))
        self.log_title.setObjectName("ai_card_title")
        log_layout.addWidget(self.log_title)
        self.operation_log_list = QListWidget()
        self.operation_log_list.setObjectName("operation_log_list")
        self.operation_log_list.setMaximumHeight(70)
        self.operation_log_list.setFocusPolicy(Qt.NoFocus)
        log_layout.addWidget(self.operation_log_list)
        self.right_layout.addWidget(self.log_card)

        # Quick actions card
        self.quick_card = QFrame()
        self.quick_card.setObjectName("ai_card")
        self.quick_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        quick_layout = QVBoxLayout(self.quick_card)
        self.quick_layout = quick_layout
        quick_layout.setContentsMargins(10, 10, 10, 10)
        quick_layout.setSpacing(10)

        self.quick_title = QLabel(self.tr_text("quick.title"))
        self.quick_title.setObjectName("ai_card_title")
        quick_layout.addWidget(self.quick_title)

        self.quick_row_1 = QHBoxLayout()
        self.quick_row_1.setSpacing(10)
        self.quick_row_2 = QHBoxLayout()
        self.quick_row_2.setSpacing(10)
        self.quick_row_3 = QHBoxLayout()
        self.quick_row_3.setSpacing(10)

        self.btn_apply = QuickActionButton(
            "🧪",
            self.tr_text("quick.apply.title"),
            self.tr_text("quick.apply.desc"),
            self.tr_text("quick.apply.short"))
        self.btn_apply.setObjectName("quick_action_btn")
        self.btn_apply.setToolTip(self.tr_text("quick.apply.tooltip"))
        self.btn_apply.clicked.connect(self.apply_ai_changes)

        self.btn_diff = QuickActionButton(
            "🔍",
            self.tr_text("quick.diff.title"),
            self.tr_text("quick.diff.desc"),
            self.tr_text("quick.diff.short"))
        self.btn_diff.setObjectName("quick_action_btn")
        self.btn_diff.setToolTip(self.tr_text("quick.diff.tooltip"))
        self.btn_diff.clicked.connect(self.show_diff)

        self.btn_undo = QuickActionButton(
            "↩️",
            self.tr_text("quick.undo.title"),
            self.tr_text("quick.undo.desc"),
            self.tr_text("quick.undo.short"))
        self.btn_undo.setObjectName("quick_action_btn")
        self.btn_undo.setToolTip(self.tr_text("quick.undo.tooltip"))
        self.btn_undo.clicked.connect(self.undo_change)

        self.btn_feedback_ai = QuickActionButton(
            "📨",
            self.tr_text("quick.feedback.title"),
            self.tr_text("quick.feedback.desc"),
            self.tr_text("quick.feedback.short"))
        self.btn_feedback_ai.setObjectName("quick_action_btn")
        self.btn_feedback_ai.setToolTip(self.tr_text("quick.feedback.tooltip"))
        self.btn_feedback_ai.clicked.connect(self.copy_failed_feedback_for_ai)
        self.btn_feedback_ai.setEnabled(False)

        self.btn_clear_ai = QuickActionButton(
            "🗑️",
            self.tr_text("quick.clear.title"),
            self.tr_text("quick.clear.desc"),
            self.tr_text("quick.clear.short"),
            danger=True)
        self.btn_clear_ai.setObjectName("quick_action_btn")
        self.btn_clear_ai.setToolTip(self.tr_text("quick.clear.tooltip"))
        self.btn_clear_ai.clicked.connect(self.clear_ai_input)

        for btn in [self.btn_apply, self.btn_diff, self.btn_undo, self.btn_feedback_ai, self.btn_clear_ai]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.quick_row_1.addWidget(self.btn_apply, 1)
        self.quick_row_1.addWidget(self.btn_diff, 1)
        self.quick_row_2.addWidget(self.btn_undo, 1)
        self.quick_row_2.addWidget(self.btn_feedback_ai, 1)
        self.quick_row_3.addWidget(self.btn_clear_ai, 1)

        self.quick_clear_placeholder = QWidget()
        self.quick_clear_placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.quick_row_3.addWidget(self.quick_clear_placeholder, 1)

        quick_layout.addLayout(self.quick_row_1)
        quick_layout.addLayout(self.quick_row_2)
        quick_layout.addLayout(self.quick_row_3)
        self.right_layout.addWidget(self.quick_card)

        self.right_bottom_spacer = QWidget()
        self.right_bottom_spacer.setMinimumHeight(0)
        self.right_bottom_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_layout.addWidget(self.right_bottom_spacer, 1)

        self.lbl_feedback_hint = QLabel(self.tr_text("feedback.hint"))
        self.lbl_feedback_hint.setObjectName("lbl_feedback_hint")
        self.lbl_feedback_hint.setWordWrap(True)
        self.lbl_feedback_hint.setMaximumHeight(48)
        self.lbl_feedback_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lbl_feedback_hint.setStyleSheet(
            "color: #16A34A; font-size: 11px; padding: 6px 9px; "
            "background: #DCFCE7; border-radius: 9px;")
        self.right_layout.addWidget(self.lbl_feedback_hint)

        self.retranslate_ui()

        # assemble splitter
        self.left_code_widget = left_widget
        left_widget.setMinimumWidth(260)
        self.right_widget.setMinimumWidth(200)
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(self.right_widget)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 2)

        saved_splitter_sizes = self.settings.get("splitter_sizes", [620, 340])
        if isinstance(saved_splitter_sizes, list) and len(saved_splitter_sizes) == 2:
            try:
                self.splitter.setSizes([int(saved_splitter_sizes[0]), int(saved_splitter_sizes[1])])
            except Exception:
                self.splitter.setSizes([620, 340])
        else:
            self.splitter.setSizes([620, 340])

        # --- overall layout ---
        main_widget = QWidget()
        self.main_container = QFrame()
        self.main_container.setObjectName("main_container")
        self.main_container.setProperty("flashState", "none")

        container_shadow = QGraphicsDropShadowEffect(self.main_container)
        container_shadow.setBlurRadius(28)
        container_shadow.setOffset(0, 8)
        container_shadow.setColor(QColor(15, 23, 42, 26))
        self.main_container.setGraphicsEffect(container_shadow)

        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        self.work_area = QWidget()
        self.work_area.setMinimumWidth(320)
        work_layout = QVBoxLayout(self.work_area)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(12)
        work_layout.addWidget(top_frame)
        work_layout.addWidget(self.splitter, 1)

        self.body_splitter = QSplitter(Qt.Horizontal)
        self.body_splitter.setObjectName("body_splitter")
        self.body_splitter.setChildrenCollapsible(False)
        self.body_splitter.addWidget(self.sidebar)
        self.body_splitter.addWidget(self.work_area)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        self._sidebar_user_resized = False
        self.body_splitter.setHandleWidth(4)
        self.body_splitter.setStyleSheet("""
            QSplitter#body_splitter::handle {
                background-color: #FFE7C2;
                width: 4px;
                margin: 0 1px;
                border-radius: 2px;
            }
            QSplitter#body_splitter::handle:hover {
                background-color: #FDBA74;
            }
            QSplitter#body_splitter::handle:pressed {
                background-color: #F97316;
            }
        """)

        self._sidebar_splitter_save_timer = QTimer(self)
        self._sidebar_splitter_save_timer.setSingleShot(True)
        self._sidebar_splitter_save_timer.setInterval(500)
        self._sidebar_splitter_save_timer.timeout.connect(self.save_settings)
        self.body_splitter.splitterMoved.connect(self._on_sidebar_splitter_moved)

        saved_sidebar_sizes = self.settings.get("sidebar_splitter_sizes", [170, 940])
        if isinstance(saved_sidebar_sizes, list) and len(saved_sidebar_sizes) == 2:
            try:
                raw_sidebar_width = int(saved_sidebar_sizes[0])
                if self.width() < 820:
                    sidebar_width = max(58, min(72, raw_sidebar_width))
                elif self.width() < 1120:
                    sidebar_width = max(76, min(110, raw_sidebar_width))
                else:
                    sidebar_width = max(130, min(320, raw_sidebar_width))

                work_width = max(260, int(saved_sidebar_sizes[1]))
                self.body_splitter.setSizes([sidebar_width, work_width])
            except Exception:
                self.body_splitter.setSizes([170, 940])
        else:
            self.body_splitter.setSizes([170, 940])

        body_layout.addWidget(self.body_splitter, 1)

        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(12)
        container_layout.addWidget(body_widget, 1)

        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.main_container)
        self.setCentralWidget(main_widget)

        self.floating_status_widget = FloatingStatusWidget(self)
        self.floating_status_widget.restore_requested.connect(self.exit_floating_mode)

        self.clear_window_flash_state()

        saved_auto_enabled = bool(self.settings.get("clipboard_auto_enabled", False))
        self.apply_clipboard_auto_state(saved_auto_enabled, persist=False)
        self.refresh_open_files_sidebar()
        self.apply_responsive_layout(force=True)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(86)
        sidebar.setMaximumWidth(320)
        sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sidebar.setStyleSheet("""
            QFrame#sidebar {
                background-color: #FFFFFF;
                border: 1px solid #E8EEF7;
                border-radius: 14px;
            }
            QPushButton#btn_new_file {
                background-color: #22C55E; color: white; border: none;
                border-radius: 10px; font-size: 13px; font-weight: 800;
                min-height: 34px;
            }
            QPushButton#btn_new_file:hover { background-color: #16A34A; }
            QLabel#sidebar_section_title {
                color: #64748B; font-size: 12px; font-weight: 800;
                background: transparent; border: none;
            }
            QLineEdit#sidebar_search {
                background-color: #F8FAFC; border: 1px solid #E3EAF5;
                border-radius: 9px; padding: 6px 9px;
                color: #334155; font-size: 12px;
            }
            QLineEdit#sidebar_search:focus {
                border: 1px solid #93C5FD; background-color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.btn_new_file = QPushButton(self.tr_text("sidebar.add_resource"))
        self.btn_new_file.setObjectName("btn_new_file")
        self.btn_new_file.setToolTip(self.tr_text("sidebar.add_resource.tooltip"))
        self.btn_new_file.setCursor(Qt.PointingHandCursor)
        self.btn_new_file.clicked.connect(self._show_add_resource_menu)
        layout.addWidget(self.btn_new_file)

        self.sidebar_title_file_manage = QLabel(self.tr_text("sidebar.file_manage"))
        self.sidebar_title_file_manage.setObjectName("sidebar_section_title")
        layout.addWidget(self.sidebar_title_file_manage)

        self.sidebar_search = QLineEdit()
        self.sidebar_search.setObjectName("sidebar_search")
        self.sidebar_search.setPlaceholderText(self.tr_text("sidebar.search.placeholder"))
        self.sidebar_search.textChanged.connect(self._on_sidebar_search_changed)
        layout.addWidget(self.sidebar_search)

        self.sidebar_title_project = QLabel(self.tr_text("sidebar.project_dir"))
        self.sidebar_title_project.setObjectName("sidebar_section_title")
        layout.addWidget(self.sidebar_title_project)

        import os as _os
        app_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        saved_roots = self.settings.get("project_roots", []) if hasattr(self, "settings") else []
        if not saved_roots:
            saved_roots = [app_root]
        self.project_tree = ProjectTreeWidget(saved_roots, self)
        active_root = self.settings.get("active_project_root", "") if hasattr(self, "settings") else ""
        if active_root:
            self.project_tree.set_active_project_root(active_root)
        self.project_tree.file_double_clicked.connect(self._on_project_file_clicked)
        self.project_tree.project_selected.connect(self._on_project_selected)
        self.project_tree.project_remove_requested.connect(self._remove_project)
        layout.addWidget(self.project_tree, 1)

        self.sidebar_drop_zone = DropResourceZone(self)
        self.sidebar_drop_zone.setToolTip(self.tr_text("widgets.drop.hint"))
        self.sidebar_drop_zone.file_dropped.connect(self._handle_drop_resource_file)
        self.sidebar_drop_zone.folder_dropped.connect(self._handle_drop_resource_folder)
        layout.addWidget(self.sidebar_drop_zone)

        return sidebar

    def _on_sidebar_splitter_moved(self, *args):
        # 小窗口下不允许目录栏被拖得过宽，否则会把中间代码区和右侧面板挤到重叠。
        if self.width() < 1120:
            self._sidebar_user_resized = False
            if hasattr(self, "body_splitter"):
                total_width = max(1, self.body_splitter.width())
                sidebar_width = 72 if self.width() < 820 else 110
                work_width = max(260, total_width - sidebar_width)
                QTimer.singleShot(0, lambda: self.body_splitter.setSizes([sidebar_width, work_width]))
            return

        self._sidebar_user_resized = True
        if hasattr(self, "_sidebar_splitter_save_timer"):
            self._sidebar_splitter_save_timer.start()

    def elide_text(self, text, label, min_width=120):
        width = max(label.width(), min_width)
        metrics = QFontMetrics(label.font())
        return metrics.elidedText(text, Qt.ElideMiddle, width)

    def update_file_path_label(self, text, color="black"):
        if hasattr(self, "lbl_file_path"):
            display_text = self.elide_text(text, self.lbl_file_path)
            self.lbl_file_path.setText(display_text)
            self.lbl_file_path.setToolTip(text)
            self.lbl_file_path.setStyleSheet(f"color: {color}; font-size: 12px;")


    def _rebuild_language_menu(self):
        """Rebuild language menu from available i18n language packs."""
        if not hasattr(self, "language_menu"):
            return

        self.language_menu.clear()
        self.language_actions = {}

        current_language = getattr(self, "current_language", "zh_CN")
        languages = get_available_languages()

        for language, language_name in sorted(languages.items(), key=lambda item: item[1].lower()):
            action = self.language_menu.addAction(language_name)
            action.setCheckable(True)
            action.setChecked(language == current_language)
            action.triggered.connect(lambda checked=False, lang=language: self.set_language(lang))
            self.language_actions[language] = action

    def _get_current_file_path_for_status(self):
        """Best-effort current file path lookup for re-translating status label."""
        try:
            current_tab_getter = getattr(self, "current_tab", None)
            if callable(current_tab_getter):
                tab = current_tab_getter()
                if tab:
                    for attr_name in ("file_path", "path", "current_file_path"):
                        value = getattr(tab, attr_name, "")
                        if value:
                            return value
        except Exception:
            pass

        for attr_name in ("current_file_path", "file_path"):
            try:
                value = getattr(self, attr_name, "")
                if value:
                    return value
            except Exception:
                pass

        try:
            tab_widget = getattr(self, "tab_widget", None)
            if tab_widget and tab_widget.currentIndex() >= 0:
                current_widget = tab_widget.currentWidget()
                if current_widget:
                    for attr_name in ("file_path", "path", "current_file_path"):
                        value = getattr(current_widget, attr_name, "")
                        if value:
                            return value

                tab_text = tab_widget.tabText(tab_widget.currentIndex()).strip()
                if tab_text:
                    return tab_text
        except Exception:
            pass

        return ""

    def _refresh_file_path_status_translation(self):
        """Refresh the current-file status label without losing the actual path."""
        if not hasattr(self, "lbl_file_path"):
            return

        file_path = self._get_current_file_path_for_status()
        if file_path:
            self.update_file_path_label(
                self.tr_text("tab.current_file") + ": " + file_path,
                "#606266")
        else:
            self.lbl_file_path.setText(self.tr_text("status.file.none"))
            self.lbl_file_path.setToolTip(self.tr_text("status.file.none"))

    def retranslate_ui(self):
        """Refresh visible UI texts after language changes."""
        if not hasattr(self, "tr_text"):
            return

        if hasattr(self, "_sync_application_title"):
            self._sync_application_title()
        else:
            self.setWindowTitle(self.tr_text("app.title"))

        if hasattr(self, "btn_load"):
            self.btn_load.setText(self.tr_text("button.load"))
            self.btn_load.setToolTip(self.tr_text("button.load"))

        if hasattr(self, "btn_save_file"):
            self.btn_save_file.setText(self.tr_text("button.save"))
            self.btn_save_file.setToolTip(self.tr_text("button.save.tooltip"))

        if hasattr(self, "btn_more"):
            self.btn_more.setText(self.tr_text("button.more"))
            self.btn_more.setToolTip(self.tr_text("menu.more.tooltip"))

        if hasattr(self, "recent_menu"):
            self.recent_menu.setTitle(self.tr_text("menu.recent_files"))

        if hasattr(self, "action_save_version"):
            self.action_save_version.setText(self.tr_text("menu.save_version"))

        if hasattr(self, "action_manage_versions"):
            self.action_manage_versions.setText(self.tr_text("menu.manage_versions"))

        if hasattr(self, "language_menu"):
            self.language_menu.setTitle(self.tr_text("menu.language"))

        if hasattr(self, "_rebuild_language_menu"):
            self._rebuild_language_menu()

        if hasattr(self, "btn_float_mode"):
            self.btn_float_mode.setText(self.tr_text("button.float"))
            self.btn_float_mode.setToolTip(self.tr_text("button.float.tooltip"))

        if hasattr(self, "lbl_auto_status"):
            self.lbl_auto_status.setText(self.tr_text("status.auto.closed"))
            self.lbl_auto_status.setToolTip(self.tr_text("status.auto.closed"))

        if hasattr(self, "lbl_file_path"):
            self._refresh_file_path_status_translation()

        if hasattr(self, "search_input"):
            self.search_input.setPlaceholderText(self.tr_text("search.placeholder"))
            self.search_input.setToolTip(self.tr_text("search.tooltip"))

        if hasattr(self, "btn_find_prev"):
            self.btn_find_prev.setText(self.tr_text("find.prev"))
            self.btn_find_prev.setToolTip(self.tr_text("find.prev.tooltip"))

        if hasattr(self, "btn_find_next"):
            self.btn_find_next.setText(self.tr_text("find.next"))
            self.btn_find_next.setToolTip(self.tr_text("find.next.tooltip"))

        if hasattr(self, "btn_copy_sel"):
            self.btn_copy_sel.setText(self.tr_text("copy.selected"))
            self.btn_copy_sel.setToolTip(self.tr_text("copy.selected.tooltip"))

        if hasattr(self, "btn_copy_all"):
            self.btn_copy_all.setText(self.tr_text("copy.all"))
            self.btn_copy_all.setToolTip(self.tr_text("copy.all.tooltip"))

        if hasattr(self, "btn_copy_project_structure"):
            self.btn_copy_project_structure.setText(self.tr_text("copy.project_structure"))
            self.btn_copy_project_structure.setToolTip(self.tr_text("copy.project_structure.tooltip"))

        if hasattr(self, "ai_title"):
            self.ai_title.setText(self.tr_text("ai.title"))

        if hasattr(self, "ai_subtitle"):
            self.ai_subtitle.setText(self.tr_text("ai.subtitle"))

        if hasattr(self, "text_ai_input"):
            self.text_ai_input.setPlaceholderText(self.tr_text("ai.placeholder"))

        if hasattr(self, "log_title"):
            self.log_title.setText(self.tr_text("log.title"))

        if hasattr(self, "quick_title"):
            self.quick_title.setText(self.tr_text("quick.title"))

        quick_button_configs = [
            (
                "btn_apply",
                "🧪",
                "quick.apply.title",
                "quick.apply.desc",
                "quick.apply.short",
                "quick.apply.tooltip",
            ),
            (
                "btn_diff",
                "🔍",
                "quick.diff.title",
                "quick.diff.desc",
                "quick.diff.short",
                "quick.diff.tooltip",
            ),
            (
                "btn_undo",
                "↩️",
                "quick.undo.title",
                "quick.undo.desc",
                "quick.undo.short",
                "quick.undo.tooltip",
            ),
            (
                "btn_feedback_ai",
                "📨",
                "quick.feedback.title",
                "quick.feedback.desc",
                "quick.feedback.short",
                "quick.feedback.tooltip",
            ),
            (
                "btn_clear_ai",
                "🗑️",
                "quick.clear.title",
                "quick.clear.desc",
                "quick.clear.short",
                "quick.clear.tooltip",
            ),
        ]
        for attr, icon_text, title_key, desc_key, short_key, tooltip_key in quick_button_configs:
            btn = getattr(self, attr, None)
            if btn:
                if hasattr(btn, "set_action_content"):
                    btn.set_action_content(
                        icon_text,
                        self.tr_text(title_key),
                        self.tr_text(desc_key),
                        self.tr_text(short_key),
                    )
                btn.setToolTip(self.tr_text(tooltip_key))

        if hasattr(self, "lbl_feedback_hint"):
            self.lbl_feedback_hint.setText(self.tr_text("feedback.hint"))

        if hasattr(self, "btn_new_file"):
            compact_sidebar = self.width() < 1120
            self.btn_new_file.setText(
                self.tr_text("sidebar.add_resource.compact")
                if compact_sidebar
                else self.tr_text("sidebar.add_resource")
            )
            self.btn_new_file.setToolTip(self.tr_text("sidebar.add_resource.tooltip"))

        if hasattr(self, "sidebar_title_file_manage"):
            self.sidebar_title_file_manage.setText(self.tr_text("sidebar.file_manage"))

        if hasattr(self, "sidebar_search"):
            self.sidebar_search.setPlaceholderText(self.tr_text("sidebar.search.placeholder"))

        if hasattr(self, "sidebar_title_project"):
            self.sidebar_title_project.setText(self.tr_text("sidebar.project_dir"))

        if hasattr(self, "preview_panel"):
            try:
                self.preview_panel._update_button_labels()
            except Exception:
                pass

        if hasattr(self, "floating_status_widget"):
            try:
                self.floating_status_widget._base_title_text = self.tr_text("widgets.float.title")
                self.floating_status_widget._update_title_feedback()
            except Exception:
                pass

        if hasattr(self, "update_recent_menu"):
            self.update_recent_menu()

        if hasattr(self, "apply_clipboard_auto_state") and hasattr(self, "clipboard_auto_enabled"):
            self.apply_clipboard_auto_state(self.clipboard_auto_enabled, persist=False)

        if hasattr(self, "operation_log_list"):
            waiting_texts = {
                "等待用户粘贴修改块",
                "Waiting for replace blocks",
                "En attente des blocs de modification",
                "ユーザーの変更ブロック貼り付けを待機中",
                "Ожидание вставки блоков изменений",
                "사용자가 수정 블록을 붙여넣기를 기다리는 중",
                self.tr_text("log.waiting"),
            }

            if self.operation_log_list.count() == 0:
                self.add_operation_log(self.tr_text("log.waiting"))
            elif self.operation_log_list.count() <= 2:
                existing_texts = [
                    self.operation_log_list.item(i).text()
                    for i in range(self.operation_log_list.count())
                    if self.operation_log_list.item(i)
                ]
                if existing_texts and all(any(waiting in text for waiting in waiting_texts) for text in existing_texts):
                    self.operation_log_list.clear()
                    self.add_operation_log(self.tr_text("log.waiting"))

        if hasattr(self, "apply_responsive_layout"):
            self.apply_responsive_layout(force=True)

    def apply_responsive_layout(self, force=False):
        compact = self.width() < 1120
        ultra_compact = self.width() < 820
        vertical_compact = self.height() < 680
        super_vertical_compact = self.height() < 560
        micro_vertical_compact = self.height() < 500

        layout_state = (compact, ultra_compact, vertical_compact, super_vertical_compact, micro_vertical_compact)
        previous_layout_state = self._compact_mode
        mode_changed = force or previous_layout_state != layout_state

        if not mode_changed:
            return

        self._compact_mode = layout_state

        # top toolbar
        if hasattr(self, "btn_load"):
            if ultra_compact:
                self.btn_load.setText(self.tr_text("button.load.compact"))
                self.btn_load.setToolTip(self.tr_text("button.load"))
                self.btn_load.setFixedWidth(46)
            elif compact:
                self.btn_load.setText(self.tr_text("button.load"))
                self.btn_load.setToolTip(self.tr_text("button.load"))
                self.btn_load.setFixedWidth(74)
            else:
                self.btn_load.setText(self.tr_text("button.load"))
                self.btn_load.setToolTip(self.tr_text("button.load"))
                self.btn_load.setMinimumWidth(78)
                self.btn_load.setMaximumWidth(16777215)

        if hasattr(self, "btn_save_file"):
            if ultra_compact:
                self.btn_save_file.setText(self.tr_text("button.save.compact"))
                self.btn_save_file.setToolTip(self.tr_text("button.save.tooltip"))
                self.btn_save_file.setFixedWidth(46)
            elif compact:
                self.btn_save_file.setText(self.tr_text("button.save"))
                self.btn_save_file.setToolTip(self.tr_text("button.save.tooltip"))
                self.btn_save_file.setFixedWidth(74)
            else:
                self.btn_save_file.setText(self.tr_text("button.save"))
                self.btn_save_file.setToolTip(self.tr_text("button.save.tooltip"))
                self.btn_save_file.setMinimumWidth(78)
                self.btn_save_file.setMaximumWidth(16777215)

        if hasattr(self, "btn_more"):
            if ultra_compact:
                self.btn_more.setText(self.tr_text("button.more.compact"))
                self.btn_more.setToolTip(self.tr_text("menu.more.tooltip"))
                self.btn_more.setFixedWidth(46)
            elif compact:
                self.btn_more.setText(self.tr_text("button.more"))
                self.btn_more.setToolTip(self.tr_text("menu.more.tooltip"))
                self.btn_more.setFixedWidth(74)
            else:
                self.btn_more.setText(self.tr_text("button.more"))
                self.btn_more.setToolTip(self.tr_text("menu.more.tooltip"))
                self.btn_more.setMinimumWidth(78)
                self.btn_more.setMaximumWidth(16777215)

        if hasattr(self, "btn_auto_clipboard"):
            if ultra_compact:
                self.btn_auto_clipboard.setText(self.tr_text("button.auto_clipboard.short"))
                self.btn_auto_clipboard.setFixedWidth(70)
            elif compact:
                self.btn_auto_clipboard.setText(self.tr_text("button.auto_clipboard.short"))
                self.btn_auto_clipboard.setFixedWidth(78)
            else:
                is_checked = self.btn_auto_clipboard.isChecked()
                self.btn_auto_clipboard.setText(
                    self.tr_text("button.auto_clipboard.on") if is_checked else self.tr_text("button.auto_clipboard.off"))
                self.btn_auto_clipboard.setMinimumWidth(112)
                self.btn_auto_clipboard.setMaximumWidth(16777215)

        if hasattr(self, "btn_float_mode"):
            if ultra_compact:
                self.btn_float_mode.setText(self.tr_text("button.float.compact"))
                self.btn_float_mode.setFixedWidth(46)
            elif compact:
                self.btn_float_mode.setText(self.tr_text("button.float"))
                self.btn_float_mode.setFixedWidth(74)
            else:
                self.btn_float_mode.setText(self.tr_text("button.float"))
                self.btn_float_mode.setMinimumWidth(76)
                self.btn_float_mode.setMaximumWidth(16777215)

        if hasattr(self, "lbl_auto_status"):
            self.lbl_auto_status.setMaximumWidth(96 if compact else 150)

        # minimum widths guard
        # 极窄窗口下必须同步降低各区域 minimumWidth，否则 splitter 拖动时会把代码区/右侧面板挤到重叠。
        if hasattr(self, "work_area"):
            self.work_area.setMinimumWidth(260 if ultra_compact else (320 if compact else 420))

        if hasattr(self, "left_code_widget"):
            self.left_code_widget.setMinimumWidth(220 if ultra_compact else (260 if compact else 320))

        if hasattr(self, "right_widget"):
            self.right_widget.setMinimumWidth(180 if ultra_compact else (200 if compact else 220))

        if hasattr(self, "sidebar"):
            self.sidebar.setMinimumWidth(58 if ultra_compact else (76 if compact else 130))

        # sidebar
        if hasattr(self, "sidebar"):
            if ultra_compact:
                self.sidebar.setMinimumWidth(58)
                self.sidebar.setMaximumWidth(72)
            elif compact:
                self.sidebar.setMinimumWidth(76)
                self.sidebar.setMaximumWidth(110)
            else:
                self.sidebar.setMinimumWidth(130)
                self.sidebar.setMaximumWidth(320)

        for widget_name in ["sidebar_title_file_manage", "sidebar_search",
                            "sidebar_title_project"]:
            widget = getattr(self, widget_name, None)
            if widget:
                widget.setVisible(not compact)

        if hasattr(self, "sidebar_drop_zone"):
            self.sidebar_drop_zone.setVisible(True)
            if hasattr(self.sidebar_drop_zone, "set_compact_mode"):
                self.sidebar_drop_zone.set_compact_mode(compact)

        if hasattr(self, "project_tree"):
            self.project_tree.set_compact_mode(compact)

        # 窗口变窄时，优先压缩左侧目录栏，保护中间编辑区和搜索工具栏。
        # 大窗口下尊重用户手动拖拽的 sidebar 宽度；小窗口下自动进入窄目录模式。
        if hasattr(self, "body_splitter"):
            total_width = max(1, self.body_splitter.width())
            current_sizes = self.body_splitter.sizes()
            current_sidebar_width = current_sizes[0] if current_sizes else 0

            if ultra_compact:
                target_sidebar_width = 58
            elif compact:
                target_sidebar_width = 76
            else:
                target_sidebar_width = max(130, min(260, current_sidebar_width or 170))

            # 极窄窗口下，目录栏不能因为用户拖动而占太多宽度，否则中间代码区会被挤到右侧面板上。
            if ultra_compact:
                target_sidebar_width = min(target_sidebar_width, 72)
            elif compact:
                target_sidebar_width = min(target_sidebar_width, 110)
            else:
                target_sidebar_width = min(target_sidebar_width, 320)

            should_adjust_sidebar = (
                force
                or ultra_compact
                or compact
                or not getattr(self, "_sidebar_user_resized", False)
            )

            if should_adjust_sidebar:
                work_width = max(260, total_width - target_sidebar_width)
                self.body_splitter.setSizes([target_sidebar_width, work_width])

        if hasattr(self, "btn_new_file"):
            self.btn_new_file.setText(self.tr_text("sidebar.add_resource.compact") if compact else self.tr_text("sidebar.add_resource"))
            self.btn_new_file.setToolTip(self.tr_text("sidebar.add_resource.tooltip"))
            self.btn_new_file.setMinimumHeight(34)

        # search row
        if hasattr(self, "search_input"):
            left_area_width = 0
            if hasattr(self, "splitter"):
                splitter_sizes = self.splitter.sizes()
                if splitter_sizes:
                    left_area_width = splitter_sizes[0]

            search_tight = compact or left_area_width < 500
            search_ultra_tight = ultra_compact or left_area_width < 390

            # 单行工具栏里，搜索框主动让位给右侧功能按钮。
            # 不使用 Expanding，避免搜索框把按钮挤出或造成重叠。
            if search_ultra_tight:
                self.search_input.setMinimumWidth(44)
                self.search_input.setMaximumWidth(64)
            elif search_tight:
                self.search_input.setMinimumWidth(52)
                self.search_input.setMaximumWidth(96)
            else:
                self.search_input.setMinimumWidth(90)
                self.search_input.setMaximumWidth(220)

            self.search_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.search_input.setPlaceholderText(
                self.tr_text("search.placeholder.micro")
                if search_ultra_tight
                else (self.tr_text("search.placeholder.short") if search_tight else self.tr_text("search.placeholder"))
            )

            if hasattr(self, "search_icon_label"):
                self.search_icon_label.setVisible(not search_ultra_tight)

        if hasattr(self, "btn_find_prev"):
            self.btn_find_prev.setVisible(True)
            if compact:
                self.btn_find_prev.setText(self.tr_text("find.prev.compact"))
                self.btn_find_prev.setToolTip(self.tr_text("find.prev.tooltip"))
                self.btn_find_prev.setFixedSize(QSize(36 if ultra_compact else 42, 42))
                self.btn_find_prev.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            else:
                self.btn_find_prev.setText(self.tr_text("find.prev"))
                self.btn_find_prev.setToolTip(self.tr_text("find.prev.tooltip"))
                self.btn_find_prev.setMinimumWidth(56)
                self.btn_find_prev.setMaximumWidth(72)
                self.btn_find_prev.setMinimumHeight(42)
                self.btn_find_prev.setMaximumHeight(42)
                self.btn_find_prev.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        if hasattr(self, "btn_find_next"):
            self.btn_find_next.setVisible(True)
            if compact:
                self.btn_find_next.setText(self.tr_text("find.next.compact"))
                self.btn_find_next.setToolTip(self.tr_text("find.next.tooltip"))
                self.btn_find_next.setFixedSize(QSize(36 if ultra_compact else 42, 42))
                self.btn_find_next.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            else:
                self.btn_find_next.setText(self.tr_text("find.next"))
                self.btn_find_next.setToolTip(self.tr_text("find.next.tooltip"))
                self.btn_find_next.setMinimumWidth(56)
                self.btn_find_next.setMaximumWidth(72)
                self.btn_find_next.setMinimumHeight(42)
                self.btn_find_next.setMaximumHeight(42)
                self.btn_find_next.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        for copy_btn_name in ["btn_copy_sel", "btn_copy_all", "btn_copy_project_structure"]:
            copy_btn = getattr(self, copy_btn_name, None)
            if copy_btn:
                copy_btn.setVisible(True)

        # copy buttons
        if hasattr(self, "btn_copy_all"):
            if compact:
                copy_btn_size = QSize(38 if ultra_compact else 42, 42)
                self.btn_copy_all.setVisible(True)
                self.btn_copy_all.setText("🥣")
                self.btn_copy_all.setToolTip(self.tr_text("copy.all.tooltip"))
                self.btn_copy_all.setFixedSize(copy_btn_size)
                self.btn_copy_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.btn_copy_all.setStyleSheet("""
                    QPushButton#btn_copy_all {
                        background-color: #F59E0B; color: white; border: none;
                        padding: 0; margin: 0; text-align: center;
                        font-size: 15px; font-weight: 800; border-radius: 10px;
                    }
                    QPushButton#btn_copy_all:hover { background-color: #D97706; }
                """)
            else:
                self.btn_copy_all.setVisible(True)
                self.btn_copy_all.setText(self.tr_text("copy.all"))
                self.btn_copy_all.setToolTip(self.tr_text("copy.all.tooltip"))
                self.btn_copy_all.setMinimumWidth(96)
                self.btn_copy_all.setMaximumWidth(130)
                self.btn_copy_all.setMinimumHeight(42)
                self.btn_copy_all.setMaximumHeight(42)
                self.btn_copy_all.resize(110, 42)
                self.btn_copy_all.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.btn_copy_all.setStyleSheet("")

        if hasattr(self, "btn_copy_project_structure"):
            if compact:
                copy_btn_size = QSize(38 if ultra_compact else 42, 42)
                self.btn_copy_project_structure.setVisible(True)
                self.btn_copy_project_structure.setText("🧭")
                self.btn_copy_project_structure.setToolTip(self.tr_text("copy.project_structure.tooltip"))
                self.btn_copy_project_structure.setFixedSize(copy_btn_size)
                self.btn_copy_project_structure.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.btn_copy_project_structure.setStyleSheet("""
                    QPushButton#btn_copy_project_structure {
                        background-color: #8B5CF6; color: white; border: none;
                        padding: 0; margin: 0; text-align: center;
                        font-size: 15px; font-weight: 800; border-radius: 10px;
                    }
                    QPushButton#btn_copy_project_structure:hover { background-color: #7C3AED; }
                """)
            else:
                self.btn_copy_project_structure.setVisible(True)
                self.btn_copy_project_structure.setText(self.tr_text("copy.project_structure"))
                self.btn_copy_project_structure.setToolTip(self.tr_text("copy.project_structure.tooltip"))
                self.btn_copy_project_structure.setMinimumWidth(98)
                self.btn_copy_project_structure.setMaximumWidth(130)
                self.btn_copy_project_structure.setMinimumHeight(42)
                self.btn_copy_project_structure.setMaximumHeight(42)
                self.btn_copy_project_structure.resize(112, 42)
                self.btn_copy_project_structure.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.btn_copy_project_structure.setStyleSheet("")

        if hasattr(self, "btn_copy_sel"):
            if compact:
                copy_btn_size = QSize(38 if ultra_compact else 42, 42)
                self.btn_copy_sel.setVisible(True)
                self.btn_copy_sel.setText("📋")
                self.btn_copy_sel.setToolTip(self.tr_text("copy.selected.tooltip"))
                self.btn_copy_sel.setFixedSize(copy_btn_size)
                self.btn_copy_sel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.btn_copy_sel.setStyleSheet("""
                    QPushButton#btn_copy_sel {
                        background-color: #3B82F6; color: white; border: none;
                        padding: 0; margin: 0; text-align: center;
                        font-size: 15px; font-weight: 800; border-radius: 10px;
                    }
                    QPushButton#btn_copy_sel:hover { background-color: #2563EB; }
                """)
            else:
                self.btn_copy_sel.setVisible(True)
                self.btn_copy_sel.setText(self.tr_text("copy.selected"))
                self.btn_copy_sel.setToolTip(self.tr_text("copy.selected.tooltip"))
                self.btn_copy_sel.setMinimumWidth(76)
                self.btn_copy_sel.setMaximumWidth(100)
                self.btn_copy_sel.setMinimumHeight(42)
                self.btn_copy_sel.setMaximumHeight(42)
                self.btn_copy_sel.resize(86, 42)
                self.btn_copy_sel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.btn_copy_sel.setStyleSheet("")

        # log card
        if hasattr(self, "log_card"):
            self.log_card.setVisible(not compact and not vertical_compact)

        # quick action buttons
        button_configs = [
            ("btn_apply", "quick.apply.tooltip"),
            ("btn_diff", "quick.diff.tooltip"),
            ("btn_undo", "quick.undo.tooltip"),
            ("btn_feedback_ai", "quick.feedback.tooltip"),
            ("btn_clear_ai", "quick.clear.tooltip"),
        ]
        for attr, tooltip_key in button_configs:
            btn = getattr(self, attr, None)
            if not btn:
                continue
            btn.setToolTip(self.tr_text(tooltip_key))
            btn.setMinimumWidth(0)
            btn.setMaximumWidth(16777215)
            if hasattr(btn, "set_compact_mode"):
                btn.set_compact_mode(compact or vertical_compact)

            if micro_vertical_compact:
                btn_height = 38
            elif super_vertical_compact:
                btn_height = 40
            elif compact or vertical_compact:
                btn_height = 42
            else:
                btn_height = 64

            btn.setMinimumHeight(btn_height)
            btn.setMaximumHeight(btn_height)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if hasattr(self, "quick_title"):
            self.quick_title.setVisible(not micro_vertical_compact)
            self.quick_title.setText(self.tr_text("quick.title.compact") if (compact or vertical_compact) else self.tr_text("quick.title"))

        if hasattr(self, "quick_card"):
            if micro_vertical_compact:
                # 3 行快捷按钮不能低于约 156px，否则按钮会垂直重叠。
                self.quick_card.setFixedHeight(162)
            elif super_vertical_compact:
                self.quick_card.setFixedHeight(168)
            elif compact:
                quick_height = 174 if vertical_compact else 186
                self.quick_card.setFixedHeight(quick_height)
            else:
                self.quick_card.setMinimumHeight(220 if vertical_compact else 262)
                self.quick_card.setMaximumHeight(240 if vertical_compact else 286)

        if hasattr(self, "quick_layout"):
            if micro_vertical_compact:
                self.quick_layout.setContentsMargins(8, 6, 8, 6)
                self.quick_layout.setSpacing(5)
            elif super_vertical_compact:
                self.quick_layout.setContentsMargins(8, 8, 8, 8)
                self.quick_layout.setSpacing(6)
            elif compact or vertical_compact:
                self.quick_layout.setContentsMargins(10, 8, 10, 8)
                self.quick_layout.setSpacing(8)
            else:
                self.quick_layout.setContentsMargins(10, 10, 10, 10)
                self.quick_layout.setSpacing(10)

        for row_name in ["quick_row_1", "quick_row_2", "quick_row_3"]:
            row_layout = getattr(self, row_name, None)
            if row_layout:
                if micro_vertical_compact:
                    row_layout.setSpacing(4)
                elif super_vertical_compact:
                    row_layout.setSpacing(6)
                else:
                    row_layout.setSpacing(8 if compact else 10)

        if hasattr(self, "quick_clear_placeholder"):
            if micro_vertical_compact:
                self.quick_clear_placeholder.setFixedHeight(38)
            elif super_vertical_compact:
                self.quick_clear_placeholder.setFixedHeight(40)
            else:
                self.quick_clear_placeholder.setFixedHeight(42 if (compact or vertical_compact) else 68)

        # right panel
        if hasattr(self, "right_layout"):
            self.right_layout.setAlignment(Qt.AlignTop)
            if micro_vertical_compact:
                self.right_layout.setContentsMargins(8, 8, 8, 8)
                self.right_layout.setSpacing(6)
            elif super_vertical_compact:
                self.right_layout.setContentsMargins(10, 10, 10, 10)
                self.right_layout.setSpacing(8)
            elif compact:
                self.right_layout.setContentsMargins(12, 12, 12, 12)
                self.right_layout.setSpacing(10)
            else:
                self.right_layout.setContentsMargins(12, 12, 12, 12)
                self.right_layout.setSpacing(12)

        if hasattr(self, "right_bottom_spacer"):
            self.right_bottom_spacer.setVisible(compact)

        if hasattr(self, "ai_title"):
            self.ai_title.setText(
                self.tr_text("ai.title.micro")
                if micro_vertical_compact
                else (self.tr_text("ai.title.compact") if (compact or vertical_compact) else self.tr_text("ai.title"))
            )

        if hasattr(self, "ai_subtitle"):
            self.ai_subtitle.setVisible(not compact and not vertical_compact)

        if hasattr(self, "text_ai_input"):
            if compact or vertical_compact:
                if micro_vertical_compact:
                    paste_height = 68
                elif super_vertical_compact:
                    paste_height = 84
                elif vertical_compact:
                    paste_height = 104
                else:
                    right_height = self.right_widget.height() if hasattr(self, "right_widget") else self.height()
                    paste_height = max(150, min(360, right_height - 320))

                self.text_ai_input.setMinimumHeight(paste_height)
                self.text_ai_input.setMaximumHeight(paste_height)
                self.text_ai_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.text_ai_input.setPlaceholderText(self.tr_text("ai.placeholder.compact"))
                self.text_ai_input.setStyleSheet("""
                    QTextEdit#ai_drop_zone {
                        background-color: #FBFFFC;
                        border: 2px dashed #86EFAC;
                        border-radius: 12px;
                        padding-top: 10px; padding-right: 10px;
                        padding-bottom: 10px; padding-left: 10px;
                        color: #334155;
                        font-family: Consolas, "Courier New", monospace;
                        font-size: 12px;
                    }
                    QTextEdit#ai_drop_zone:focus {
                        border: 2px dashed #22C55E;
                        background-color: #FFFFFF;
                    }
                """)
            else:
                self.text_ai_input.setMinimumHeight(110)
                self.text_ai_input.setMaximumHeight(16777215)
                self.text_ai_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.text_ai_input.setPlaceholderText(self.tr_text("ai.placeholder"))
                self.text_ai_input.setStyleSheet("")

        if hasattr(self, "lbl_feedback_hint"):
            self.lbl_feedback_hint.setVisible(not micro_vertical_compact)
            if compact or vertical_compact:
                self.lbl_feedback_hint.setMaximumHeight(22 if super_vertical_compact else 30)
                self.lbl_feedback_hint.setText(self.tr_text("feedback.hint.compact"))
                self.lbl_feedback_hint.setStyleSheet(
                    "color: #16A34A; font-size: 11px; padding: 2px 7px; "
                    "background: #DCFCE7; border-radius: 8px;")
            else:
                self.lbl_feedback_hint.setMaximumHeight(48)
                self.lbl_feedback_hint.setText(self.tr_text("feedback.hint"))
                self.lbl_feedback_hint.setStyleSheet(
                    "color: #16A34A; font-size: 11px; padding: 6px 9px; "
                    "background: #DCFCE7; border-radius: 9px;")

        tab_widget = (getattr(self, "tabs", None) or getattr(self, "tab_widget", None)
                      or getattr(self, "editor_tabs", None))
        if tab_widget:
            tab_widget.setStyleSheet("""
                QTabWidget::pane {
                    background: #FFFFFF;
                    border: 1px solid #E5EEF9;
                    border-radius: 0 0 12px 12px;
                    top: -1px;
                }
                QTabBar::tab {
                    background: #FFFFFF; color: #2F80ED;
                    border: 1px solid #E5EEF9;
                    border-bottom: 1px solid #FFFFFF;
                    border-top-left-radius: 8px; border-top-right-radius: 8px;
                    padding: 8px 28px 8px 12px;
                    margin-right: 2px; margin-bottom: -1px;
                    font-weight: 800;
                }
                QTabBar::tab:selected {
                    background: #FFFFFF;
                    border-color: #D8E4F2;
                    border-bottom-color: #FFFFFF;
                }
                QTabBar::tab:!selected {
                    background: #F8FAFC; color: #64748B;
                }
            """)

        # splitter ratios
        # 不要写死 [560, 200] / [660, 240]，极窄窗口会导致左右区域总宽超过可用宽度并产生覆盖。
        if hasattr(self, "splitter") and (force or mode_changed):
            total_width = max(1, self.splitter.width())

            if ultra_compact:
                right_width = max(180, min(220, int(total_width * 0.34)))
                left_width = max(220, total_width - right_width)
                self.splitter.setSizes([left_width, right_width])
            elif compact:
                right_width = max(200, min(260, int(total_width * 0.32)))
                left_width = max(260, total_width - right_width)
                self.splitter.setSizes([left_width, right_width])

        if hasattr(self, "body_splitter"):
            total_width = max(1, self.body_splitter.width())
            current_sizes = self.body_splitter.sizes()
            if current_sizes:
                current_sidebar_width = current_sizes[0]
                if ultra_compact and current_sidebar_width > 72:
                    self.body_splitter.setSizes([72, max(260, total_width - 72)])
                elif compact and current_sidebar_width > 110:
                    self.body_splitter.setSizes([110, max(260, total_width - 110)])

        if force:
            self.refresh_open_files_sidebar()

    def _parse_and_preview(self):
        text = self.text_ai_input.toPlainText()
        blocks = extract_replace_blocks(text)
        if blocks:
            self.preview_panel.populate(blocks)
            self.preview_panel.setVisible(True)
        else:
            self.preview_panel.setVisible(False)

    def _on_project_selected(self, project_root):
        if not project_root:
            return

        self.settings["active_project_root"] = project_root
        if hasattr(self, "apply_active_project_filter"):
            self.apply_active_project_filter()

        self.save_settings()
        self.add_operation_log(
            self.tr_text(
                "project.log.switched",
                project_name=os.path.basename(project_root) or project_root),
            "success")

    def _on_project_file_clicked(self, file_path):
        self.open_file_in_tab(file_path)

    def _on_sidebar_search_changed(self):
        if hasattr(self, "project_tree"):
            keyword = self.sidebar_search.text() if self.sidebar_search else ""
            self.project_tree.filter_by_keyword(keyword)

    def _show_add_resource_menu(self):
        """左侧主按钮统一入口：打开文件、添加项目目录、新建文件。"""
        menu = QMenu(self)

        action_open_file = menu.addAction(self.tr_text("dialog.add.open_file"))
        action_add_folder = menu.addAction(self.tr_text("dialog.add.add_folder"))
        menu.addSeparator()
        action_new_file = menu.addAction(self.tr_text("dialog.add.new_file"))

        action = menu.exec(self.btn_new_file.mapToGlobal(self.btn_new_file.rect().bottomLeft()))
        if action == action_open_file:
            self._add_file_resource()
        elif action == action_add_folder:
            self._add_folder_resource()
        elif action == action_new_file:
            self.create_new_file()

    def _add_file_resource(self):
        """选择文件并打开，同时尽量自动识别项目根目录。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr_text("dialog.add.open_file.title"),
            "",
            self.tr_text("dialog.add.file_filter")
        )
        if not file_path:
            return

        file_path = os.path.normpath(os.path.abspath(file_path))
        project_root = ""

        if file_path.lower().endswith(".py") and hasattr(self, "detect_project_root_from_python_file"):
            project_root = self.detect_project_root_from_python_file(file_path)
        else:
            project_root = os.path.dirname(file_path)

        added = False
        if project_root and hasattr(self, "add_project_root_if_missing"):
            added = self.add_project_root_if_missing(project_root)

        self.open_file_in_tab(file_path)

        if added:
            self.refresh_project_roots_ui()
            self.save_settings()
            self.add_operation_log(
                self.tr_text(
                    "project.log.detected_added",
                    project_name=os.path.basename(project_root) or project_root),
                "success")
        else:
            self.refresh_open_files_sidebar()
            self.save_settings()

    def _add_folder_resource(self):
        """选择文件夹并添加到项目目录。"""
        chosen = QFileDialog.getExistingDirectory(
            self,
            self.tr_text("dialog.add.folder.title"))
        if not chosen:
            return

        chosen = os.path.normpath(os.path.abspath(chosen))
        if not os.path.isdir(chosen):
            QMessageBox.warning(
                self,
                self.tr_text("tab.notice.title"),
                self.tr_text("dialog.add.folder_missing"))
            return

        if hasattr(self, "add_project_root_if_missing"):
            added = self.add_project_root_if_missing(chosen)
        else:
            current = [
                os.path.normpath(os.path.abspath(path))
                for path in self.project_tree.get_project_roots()
                if path
            ]
            if chosen in current:
                added = False
            else:
                current.append(chosen)
                self.settings["project_roots"] = current
                added = True

        if not added:
            self.add_operation_log(
                self.tr_text("project.log.exists", project_name=os.path.basename(chosen)),
                "info")
            return

        self.settings["active_project_root"] = chosen
        self.refresh_project_roots_ui()
        if hasattr(self.project_tree, "set_active_project_root"):
            self.project_tree.set_active_project_root(chosen)
        if hasattr(self, "apply_active_project_filter"):
            self.apply_active_project_filter()
        self.save_settings()
        self.add_operation_log(
            self.tr_text("project.log.added", project_name=os.path.basename(chosen)),
            "success")

    def _add_project(self):
        """兼容旧入口：统一转到添加项目文件夹。"""
        self._add_folder_resource()

    def _remove_project(self, path):
        current = self.project_tree.get_project_roots()
        if len(current) <= 1:
            QMessageBox.information(
                self,
                self.tr_text("tab.notice.title"),
                self.tr_text("project.remove.keep_one"))
            return
        reply = QMessageBox.question(
            self,
            self.tr_text("project.remove.confirm.title"),
            self.tr_text(
                "project.remove.confirm.message",
                project_name=os.path.basename(path)),
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        current = [p for p in current if p != path]
        self.project_tree.set_project_roots(current)
        self.settings["project_roots"] = current

        if self.settings.get("active_project_root") == path:
            next_root = current[0] if current else ""
            self.settings["active_project_root"] = next_root
            if next_root:
                self.project_tree.set_active_project_root(next_root)
            if hasattr(self, "apply_active_project_filter"):
                self.apply_active_project_filter()

        self.save_settings()
        self.add_operation_log(
            self.tr_text("project.log.removed", project_name=os.path.basename(path)),
            "info")
