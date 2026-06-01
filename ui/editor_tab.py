"""Single editor tab widget containing a CodeEditor with syntax highlighting."""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from .code_editor import CodeEditor
from .highlighter import PythonHighlighter


class EditorTab(QWidget):
    content_reload_requested = Signal(str)

    def __init__(self, file_path, content):
        super().__init__()
        self.file_path = file_path
        self.history = [content]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_code = CodeEditor()
        self.highlighter = PythonHighlighter(self.text_code.document())
        self.text_code.setPlainText(content)

        layout.addWidget(self.text_code)
