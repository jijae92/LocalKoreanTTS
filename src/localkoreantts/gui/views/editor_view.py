"""Text and file input views for the Local Korean TTS GUI."""
from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Signal  # type: ignore[import-not-found]
from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class EditorView(QWidget):  # type: ignore[misc]
    """Widget providing a markdown/text editor."""

    text_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText("여기에 텍스트나 마크다운을 입력하세요…")
        self._editor.textChanged.connect(self._on_text_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("텍스트 입력", self))
        layout.addWidget(self._editor)

    def current_text(self) -> str:
        """Return the current editor contents."""
        return cast(str, self._editor.toPlainText())

    def set_text(self, value: str) -> None:
        """Replace the editor contents."""
        self._editor.setPlainText(value)

    def focus_editor(self) -> None:
        """Give focus to the text editor."""
        self._editor.setFocus()

    def _on_text_changed(self) -> None:
        self.text_changed.emit(self.current_text())


class FileInputView(QWidget):  # type: ignore[misc]
    """Widget used to select an input text file."""

    file_changed = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path_edit = QLineEdit(self)
        self._path_edit.setPlaceholderText("텍스트 또는 마크다운 파일을 선택하세요…")
        self._path_edit.textChanged.connect(self._emit_change)

        browse_button = QPushButton("찾아보기…", self)
        browse_button.clicked.connect(self.browse_for_file)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("파일 선택", self))
        row = QHBoxLayout()
        row.addWidget(self._path_edit, stretch=1)
        row.addWidget(browse_button)
        layout.addLayout(row)

    def current_path(self) -> Path | None:
        """Return the currently selected path."""
        text = self._path_edit.text().strip()
        if not text:
            return None
        return Path(text).expanduser()

    def set_path(self, path: Path) -> None:
        """Update the selected path."""
        self._path_edit.setText(str(path))

    def clear(self) -> None:
        """Clear the current selection."""
        self._path_edit.clear()

    def browse_for_file(self) -> None:
        """Open a file dialog and update the selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "입력 파일 선택",
            "",
            "텍스트 파일 (*.txt *.md);;모든 파일 (*)",
        )
        if file_path:
            path = Path(file_path)
            self.set_path(path)
            self.file_changed.emit(path)

    def _emit_change(self, _: str) -> None:
        path = self.current_path()
        if path is not None:
            self.file_changed.emit(path)
