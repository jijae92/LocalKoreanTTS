"""Console-style log view with PII scrubbing."""
from __future__ import annotations

# ruff: noqa: I001

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from ... import pii


class LogView(QPlainTextEdit):
    """Read-only log pane with basic level colouring."""

    COLOR_MAP = {
        "DEBUG": QColor("#A9A9A9"),
        "INFO": QColor("#E0E0E0"),
        "WARNING": QColor("#F4A460"),
        "ERROR": QColor("#FF6B6B"),
        "CRITICAL": QColor("#FF4D4F"),
    }

    def __init__(self, parent: QPlainTextEdit | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5_000)
        self.setPlaceholderText("로그 출력 (민감 정보는 자동으로 마스킹됩니다)…")

    def append_message(self, level: str, message: str) -> None:
        """Append a log line with scrubbed text and colour."""
        sanitized = pii.scrub(message)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(self.COLOR_MAP.get(level.upper(), QColor("#FFFFFF")))
        cursor.insertText(f"[{level}] {sanitized}\n", fmt)
        self.setTextCursor(cursor)
