"""Tests for GUI status badges and settings validation."""
from __future__ import annotations

# ruff: noqa: I001

import os

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6.QtWidgets")


def test_status_badge_flags_missing_ffmpeg(qtbot, tmp_path):
    from localkoreantts.gui.main_window import MainWindow  # type: ignore[import]
    from localkoreantts.gui.views.settings_dialog import SettingsData  # type: ignore[import]

    window = MainWindow()
    qtbot.addWidget(window)

    model = tmp_path / "model.bin"
    model.write_text("m")
    cache = tmp_path / "cache"
    cache.mkdir()

    window._settings_data = SettingsData(
        model_path=model,
        cache_dir=cache,
        ffmpeg_bin="ffmpeg-missing-cmd",
        sample_rate=22_050,
        default_speed=1.0,
    )
    window._update_status_badges()
    assert "✖" in window._status_badge_label.text()


def test_status_badge_flags_valid_ffmpeg(qtbot, tmp_path):
    from localkoreantts.gui.main_window import MainWindow  # type: ignore[import]
    from localkoreantts.gui.views.settings_dialog import SettingsData  # type: ignore[import]

    window = MainWindow()
    qtbot.addWidget(window)

    model = tmp_path / "model.bin"
    model.write_text("m")
    cache = tmp_path / "cache"
    cache.mkdir()

    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.write_text("#!/bin/sh\necho 'ffmpeg version 1'\n")
    os.chmod(fake_ffmpeg, 0o755)

    window._settings_data = SettingsData(
        model_path=model,
        cache_dir=cache,
        ffmpeg_bin=str(fake_ffmpeg),
        sample_rate=22_050,
        default_speed=1.0,
    )
    window._update_status_badges()
    assert "✔" in window._status_badge_label.text()
