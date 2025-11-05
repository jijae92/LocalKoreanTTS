"""Tests ensuring GUI log output masks PII."""
from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6.QtWidgets")


def test_log_view_masks_pii(qtbot) -> None:
    from localkoreantts.gui.views.log_view import LogView  # type: ignore[import]

    view = LogView()
    qtbot.addWidget(view)
    message = "테스트 카드번호 4111-1111-1111-1111 주민번호 900101-1234567"
    view.append_message("INFO", message)
    output = view.toPlainText()
    assert "4111" not in output
    assert "900101" not in output
    assert not any(char.isdigit() for char in output)
