"""PII scrubbing tests for log view."""
from __future__ import annotations

# ruff: noqa: I001

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6.QtWidgets")


def test_log_view_masks_values(qtbot) -> None:
    from localkoreantts.gui.views.log_view import LogView  # type: ignore[import]

    view = LogView()
    qtbot.addWidget(view)
    message = "카드번호 4111-1111-1111-1111 주민번호 900101-1234567"
    view.append_message("INFO", message)
    text = view.toPlainText()
    assert "4111" not in text
    assert "1234567" not in text
