"""Translation helpers for the GUI."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QCoreApplication, QLocale, QTranslator  # type: ignore[import]


AVAILABLE_LANGUAGES = {
    "ko-KR": "한국어",
    "en-US": "English",
}


class TranslatorManager:
    """Manage Qt translators for runtime language switching."""

    def __init__(self) -> None:
        self._translator: Optional[QTranslator] = None
        self._current_locale = QLocale.system().name()

    @property
    def current_language(self) -> str:
        return self._current_locale

    def load_language(self, locale_name: str) -> bool:
        if locale_name not in AVAILABLE_LANGUAGES:
            return False
        translator = QTranslator()
        qm_path = Path(__file__).resolve().parent / "resources" / f"i18n/{locale_name}.qm"
        if not translator.load(str(qm_path)):
            return False
        if self._translator:
            QCoreApplication.removeTranslator(self._translator)
        QCoreApplication.installTranslator(translator)
        self._translator = translator
        self._current_locale = locale_name
        return True

TRANSLATOR_MANAGER = TranslatorManager()


def tr(context: str, text: str) -> str:
    return QCoreApplication.translate(context, text)
