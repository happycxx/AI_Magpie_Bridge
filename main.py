"""AI 鹊桥 — entry point."""
import sys
import os
import traceback
import datetime
import faulthandler
import atexit

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(APP_DIR, "logs")
CRASH_LOG_PATH = os.path.join(LOG_DIR, "crash.log")
_FAULT_LOG_FILE = None

sys.path.insert(0, APP_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from app.i18n import DEFAULT_LANGUAGE, translate
from app.main_window import AICoderApp


def _ensure_log_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass


def write_crash_log(message):
    """尽量安全地写入崩溃日志；任何异常都不能反向影响主程序。"""
    try:
        _ensure_log_dir()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CRASH_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}] {message}\n")
    except Exception:
        pass


def handle_exception(exc_type, exc_value, exc_traceback):
    """捕获 Python 层未处理异常。"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    write_crash_log("UNCAUGHT PYTHON EXCEPTION\n" + detail)
    try:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    except Exception:
        pass


def qt_message_handler(mode, context, message):
    """记录 Qt 层 warning/critical/fatal 信息，便于定位 PySide 隐性问题。"""
    try:
        level_map = {
            QtMsgType.QtDebugMsg: "QT_DEBUG",
            QtMsgType.QtInfoMsg: "QT_INFO",
            QtMsgType.QtWarningMsg: "QT_WARNING",
            QtMsgType.QtCriticalMsg: "QT_CRITICAL",
            QtMsgType.QtFatalMsg: "QT_FATAL",
        }
        level = level_map.get(mode, "QT_MESSAGE")
        location = ""
        if context and getattr(context, "file", None):
            location = f" ({context.file}:{context.line})"
        write_crash_log(f"{level}{location}: {message}")
    except Exception:
        pass


def install_crash_logger():
    """安装全局异常/Qt消息/faulthandler 日志。"""
    global _FAULT_LOG_FILE

    _ensure_log_dir()
    write_crash_log("APP START")

    sys.excepthook = handle_exception
    qInstallMessageHandler(qt_message_handler)

    try:
        _FAULT_LOG_FILE = open(CRASH_LOG_PATH, "a", encoding="utf-8")
        faulthandler.enable(file=_FAULT_LOG_FILE, all_threads=True)
    except Exception as e:
        write_crash_log(f"faulthandler enable failed: {e}")


def close_crash_logger():
    global _FAULT_LOG_FILE

    write_crash_log("APP EXIT")
    try:
        if _FAULT_LOG_FILE:
            _FAULT_LOG_FILE.flush()
            _FAULT_LOG_FILE.close()
            _FAULT_LOG_FILE = None
    except Exception:
        pass

GLOBAL_QSS = """
    QMainWindow {
        background-color: #F3F7FD;
    }

    QWidget {
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        color: #1F2937;
    }

    QFrame#top_frame {
        background-color: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E8EEF7;
    }

    QPushButton {
        background-color: #FFFFFF;
        border: 1px solid #E3EAF5;
        color: #475569;
        padding: 6px 12px;
        border-radius: 8px;
        font-size: 12px;
        min-height: 22px;
        font-weight: 600;
    }

    QPushButton::menu-indicator {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 10px;
        left: -2px;
    }

    QPushButton:hover {
        color: #2563EB;
        border-color: #BFDBFE;
        background-color: #F8FBFF;
    }

    QPushButton:pressed {
        color: #1D4ED8;
        border-color: #93C5FD;
        background-color: #EFF6FF;
    }

    QPushButton#btn_apply {
        background-color: #22C55E;
        color: white;
        border: none;
        font-size: 13px;
        font-weight: 800;
    }

    QPushButton#btn_apply:hover {
        background-color: #16A34A;
    }

    QPushButton#btn_copy_all {
        background-color: #F59E0B;
        color: white;
        border: none;
        font-weight: 800;
    }

    QPushButton#btn_copy_all:hover {
        background-color: #D97706;
    }

    QPushButton#btn_copy_sel {
        background-color: #3B82F6;
        color: white;
        border: none;
        font-weight: 800;
    }

    QPushButton#btn_copy_sel:hover {
        background-color: #2563EB;
    }

    QPushButton#btn_feedback_ai {
        background-color: #EEF2FF;
        color: #4F46E5;
        border: 1px solid #E0E7FF;
        font-weight: 800;
    }

    QPushButton#btn_feedback_ai:hover {
        background-color: #E0E7FF;
    }

    QPushButton#btn_feedback_ai:disabled {
        background-color: #F1F5F9;
        color: #CBD5E1;
        border: 1px solid #E2E8F0;
    }

    QPushButton#btn_more {
        font-weight: 800;
        min-width: 72px;
    }

    QPushButton#btn_more:hover {
        background-color: #F8FAFC;
    }

    QTextEdit {
        border: 1px solid #E3EAF5;
        border-radius: 14px;
        padding: 12px;
        background-color: #FFFFFF;
        font-family: Consolas, "Courier New", monospace;
        font-size: 13px;
        selection-background-color: #DBEAFE;
        selection-color: #1E3A8A;
    }

    QTextEdit:focus {
        border: 1px solid #86EFAC;
        background-color: #FFFFFF;
    }

    QLineEdit {
        border: 1px solid #E3EAF5;
        border-radius: 10px;
        padding: 7px 10px;
        background-color: #FFFFFF;
        font-family: Consolas, "Courier New", monospace;
        font-size: 13px;
        selection-background-color: #DBEAFE;
        selection-color: #1E3A8A;
    }

    QLineEdit:focus {
        border: 1px solid #60A5FA;
        background-color: #FFFFFF;
    }

    QLabel {
        color: #334155;
        font-size: 12px;
        font-weight: 700;
        background: transparent;
    }

    QLabel#lbl_feedback_hint {
        font-weight: 500;
        line-height: 1.5;
        border-radius: 10px;
    }

    QTabWidget::pane {
        border: 1px solid #E8EEF7;
        border-radius: 14px;
        background-color: #FFFFFF;
        top: -1px;
    }

    QTabBar::tab {
        padding: 8px 14px;
        background: #F8FAFC;
        color: #64748B;
        border: 1px solid #E8EEF7;
        border-bottom: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        margin-right: 4px;
    }

    QTabBar::tab:selected {
        background: #FFFFFF;
        color: #16A34A;
        font-weight: 800;
    }

    QTabBar::close-button {
        margin-left: 6px;
    }

    QSplitter::handle {
        background-color: #EEF2F7;
        width: 8px;
        margin: 0 6px;
        border-radius: 4px;
    }

    QSplitter::handle:hover {
        background-color: #DDE7F5;
    }

    QMenu {
        background-color: #FFFFFF;
        border: 1px solid #E3EAF5;
        border-radius: 10px;
        padding: 6px;
    }

    QMenu::item {
        padding: 8px 16px;
        border-radius: 7px;
        color: #334155;
    }

    QMenu::item:selected {
        background-color: #EFF6FF;
        color: #2563EB;
    }
"""

if __name__ == "__main__":
    install_crash_logger()
    atexit.register(close_crash_logger)

    try:
        app = QApplication(sys.argv)
        app_title = translate("app.title", DEFAULT_LANGUAGE)
        app.setApplicationName(app_title)
        app.setApplicationDisplayName(app_title)
        app.setStyleSheet(GLOBAL_QSS)

        window = AICoderApp()
        window.destroyed.connect(lambda: write_crash_log("MAIN WINDOW DESTROYED"))
        window.show()

        exit_code = app.exec()
        write_crash_log(f"APP EXEC FINISHED, exit_code={exit_code}")
        sys.exit(exit_code)
    except Exception:
        write_crash_log("FATAL ERROR IN MAIN\n" + traceback.format_exc())
        raise
