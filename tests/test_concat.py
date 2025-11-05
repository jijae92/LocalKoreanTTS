"""Tests for WAV concatenation helper."""
from __future__ import annotations

import math
import shutil
import wave
from pathlib import Path

import pytest

from localkoreantts.utils import concat_wavs_with_silence


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
def test_concat_creates_file(tmp_path: Path) -> None:
    sample_rate = 8000
    durations = [0.05, 0.04, 0.03]
    wav_paths: list[Path] = []

    for index, duration in enumerate(durations):
        wav_path = tmp_path / f"chunk_{index}.wav"
        _write_silence_wav(wav_path, sample_rate=sample_rate, duration=duration)
        wav_paths.append(wav_path)

    output_path = tmp_path / "merged.wav"
    concat_wavs_with_silence(
        [str(path) for path in wav_paths],
        str(output_path),
        silence_duration=0.1,
    )

    assert output_path.exists()

    with wave.open(str(output_path), "rb") as wav_file:
        assert wav_file.getframerate() == sample_rate
        total_frames = wav_file.getnframes()

    expected_frames = sum(int(sample_rate * d) for d in durations)
    expected_frames += int(sample_rate * 0.1) * (len(durations) - 1)
    # allow 20ms variation due to encoding rounding
    tolerance = int(sample_rate * 0.02)
    assert math.isclose(total_frames, expected_frames, abs_tol=tolerance)


def _write_silence_wav(path: Path, *, sample_rate: int, duration: float) -> None:
    frames = int(sample_rate * duration)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
