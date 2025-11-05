"""Audio preview tests for GUI player controls."""
from __future__ import annotations

# ruff: noqa: I001

import io
import wave
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
QtMultimedia = pytest.importorskip("PySide6.QtMultimedia")


def _make_wav(path: Path, *, sample_rate: int = 8_000, duration: float = 0.05) -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = int(sample_rate * duration)
        wav_file.writeframes(b"\x00\x00" * frames)
    path.write_bytes(buffer.getvalue())


@pytest.mark.skipif(
    getattr(QtMultimedia, "QMediaPlayer", None) is None,
    reason="PySide6 QtMultimedia not available",
)
def test_audio_preview_controls(qtbot, tmp_path: Path) -> None:
    from PySide6.QtMultimedia import QMediaPlayer  # type: ignore[import]

    from localkoreantts.gui.main_window import MainWindow  # type: ignore[import]

    window = MainWindow()
    qtbot.addWidget(window)

    if window._player is None:  # type: ignore[attr-defined]
        pytest.skip("Player not initialised")

    wav_path = tmp_path / "sample.wav"
    _make_wav(wav_path)
    window._last_output_path = wav_path
    window._load_player_source(wav_path)  # type: ignore[attr-defined]

    window._start_playback()  # type: ignore[attr-defined]
    qtbot.wait_until(
        lambda: window._player.playbackState() == QMediaPlayer.PlayingState,  # type: ignore[attr-defined]
        timeout=2000,
    )

    window._pause_playback()  # type: ignore[attr-defined]
    qtbot.wait_until(
        lambda: window._player.playbackState() == QMediaPlayer.PausedState,  # type: ignore[attr-defined]
        timeout=2000,
    )

    window._stop_playback()  # type: ignore[attr-defined]
    qtbot.wait_until(
        lambda: window._player.playbackState() == QMediaPlayer.StoppedState,  # type: ignore[attr-defined]
        timeout=2000,
    )
