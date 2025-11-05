from __future__ import annotations

import sys
from typing import NoReturn

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> NoReturn:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())