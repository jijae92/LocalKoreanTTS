"""Signal-level tests for the GUI worker layer."""
from __future__ import annotations

# ruff: noqa: I001

import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from localkoreantts.gui.pipeline import JobCancelled, SynthJobConfig
from localkoreantts.gui.workers import SynthWorker

pytest.importorskip("pytestqt")

try:  # pragma: no cover - optional dependency
    from PySide6.QtCore import QThread, QTimer  # type: ignore[import]
    from PySide6.QtTest import QSignalSpy  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    QThread = None  # type: ignore[assignment]
    QTimer = None  # type: ignore[assignment]
    QSignalSpy = None  # type: ignore[assignment]


def _install_fake_pipeline(monkeypatch: pytest.MonkeyPatch, func: Callable) -> None:
    monkeypatch.setattr(
        "localkoreantts.gui.workers.synth_worker.run_synthesis_pipeline",
        func,
    )


def test_worker_success_signals(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if QThread is None or QSignalSpy is None:
        pytest.skip("PySide6 not installed")
    def fake_pipeline(config: SynthJobConfig, hooks):
        hooks.on_stage("chunking")
        total = 3
        for idx in range(1, total + 1):
            if hooks.should_cancel():  # pragma: no cover - defensive
                raise JobCancelled()
            hooks.on_stage("chunk_synth")
            hooks.on_progress(idx, total)
            hooks.on_chunk_done(idx, total)
            time.sleep(0.01)
        hooks.on_stage("finalising")
        output = config.output_dir / "result.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"RIFF")
        hooks.on_stage("completed")
        return SimpleNamespace(output_path=output)

    _install_fake_pipeline(monkeypatch, fake_pipeline)

    config = SynthJobConfig(
        job_id=1,
        text="sample",
        input_path=None,
        output_dir=tmp_path,
        output_format="wav",
        model_path=tmp_path / "model.onnx",
        cache_dir=tmp_path / "cache",
        ffmpeg_bin="ffmpeg",
        speed=1.0,
        sample_rate=22_050,
        silence_milliseconds=0,
    )

    worker = SynthWorker(config)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    progress_spy = QSignalSpy(worker.progress)
    chunk_spy = QSignalSpy(worker.chunk_done)
    stage_spy = QSignalSpy(worker.stage)
    finished_spy = QSignalSpy(worker.finished)
    error_spy = QSignalSpy(worker.error)
    cancelled_spy = QSignalSpy(worker.cancelled)

    thread.start()
    qtbot.waitSignal(worker.finished, timeout=2000)
    thread.quit()
    qtbot.waitSignal(thread.finished, timeout=2000)

    assert len(finished_spy) == 1
    assert Path(str(finished_spy[0][0])).exists()
    assert len(progress_spy) >= 1
    assert [tuple(sig) for sig in chunk_spy][-1] == (3, 3)
    stages = [sig[0] for sig in stage_spy]
    assert "completed" in stages
    assert not error_spy
    assert not cancelled_spy


def test_worker_cancel(qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if QThread is None or QSignalSpy is None or QTimer is None:
        pytest.skip("PySide6 not installed")
    def fake_pipeline(config: SynthJobConfig, hooks):
        hooks.on_stage("chunking")
        for idx in range(1, 5):
            if hooks.should_cancel():
                raise JobCancelled()
            hooks.on_progress(idx, 10)
            hooks.on_chunk_done(idx, 10)
            hooks.on_stage("chunk_synth")
            time.sleep(0.02)
        output = config.output_dir / "result.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"RIFF")
        return SimpleNamespace(output_path=output)

    _install_fake_pipeline(monkeypatch, fake_pipeline)

    config = SynthJobConfig(
        job_id=2,
        text="cancel",
        input_path=None,
        output_dir=tmp_path,
        output_format="wav",
        model_path=tmp_path / "model.onnx",
        cache_dir=tmp_path / "cache",
        ffmpeg_bin="ffmpeg",
        speed=1.0,
        sample_rate=22_050,
        silence_milliseconds=0,
    )

    worker = SynthWorker(config)
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    cancelled_spy = QSignalSpy(worker.cancelled)
    error_spy = QSignalSpy(worker.error)

    def trigger_cancel() -> None:
        worker.request_cancel()

    QTimer.singleShot(30, trigger_cancel)
    thread.start()
    qtbot.waitSignal(worker.cancelled, timeout=2000)
    thread.quit()
    qtbot.waitSignal(thread.finished, timeout=2000)

    assert cancelled_spy
    assert not error_spy
