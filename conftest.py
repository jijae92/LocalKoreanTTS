"""Global pytest configuration for LocalKoreanTTS."""
from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    """Configure pytest environment for GUI tests."""
    # Use offscreen platform for Qt tests in headless environments
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


def pytest_collection_modifyitems(config, items):
    """Skip worker tests in headless/offscreen environments."""
    skip_worker = pytest.mark.skip(
        reason="Worker tests require real display (skip in headless/offscreen environment)"
    )
    for item in items:
        if "test_worker" in item.nodeid and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            item.add_marker(skip_worker)


@pytest.fixture(scope="session")
def qapp():
    """
    QApplication fixture for GUI tests.

    Creates a single QApplication instance for the entire test session.
    pytest-qt's qtbot automatically uses this when available.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app
