from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    """Minimal main window for LocalKoreanTTS GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LocalKoreanTTS")
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("LocalKoreanTTS GUI is alive."))
        self.setCentralWidget(central)
