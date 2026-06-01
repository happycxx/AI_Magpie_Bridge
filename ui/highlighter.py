"""Python syntax highlighter (One Dark theme style)."""
import re
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#C678DD"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = ["and", "as", "assert", "break", "class", "continue", "def",
                    "del", "elif", "else", "except", "False", "finally", "for",
                    "from", "global", "if", "import", "in", "is", "lambda", "None",
                    "nonlocal", "not", "or", "pass", "raise", "return", "True",
                    "try", "while", "with", "yield"]
        for word in keywords:
            self.highlighting_rules.append((re.compile(rf"\b{word}\b"), keyword_format))

        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#56B6C2"))
        builtins = ["print", "len", "range", "str", "int", "float", "list", "dict",
                    "set", "tuple", "open", "super", "isinstance", "type", "dir",
                    "getattr", "setattr"]
        for word in builtins:
            self.highlighting_rules.append((re.compile(rf"\b{word}\b"), builtin_format))

        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#E5C07B"))
        self.highlighting_rules.append((re.compile(r"\bclass\s+(\w+)"), class_format))

        func_format = QTextCharFormat()
        func_format.setForeground(QColor("#61AFEF"))
        self.highlighting_rules.append((re.compile(r"\bdef\s+(\w+)"), func_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#98C379"))
        self.highlighting_rules.append((re.compile(r'".*?"'), string_format))
        self.highlighting_rules.append((re.compile(r"'.*?'"), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#D19A66"))
        self.highlighting_rules.append((re.compile(r"\b[0-9]+\b"), number_format))

        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#D19A66"))
        self.highlighting_rules.append((re.compile(r"@[^\n]*"), decorator_format))

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#5C6370"))
        self.comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r"#[^\n]*"), self.comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)
