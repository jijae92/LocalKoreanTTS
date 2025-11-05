"""Tests for GUI worker lifecycle."""
from __future__ import annotations

# ruff: noqa: I001

import time
from collections.abc import Callable

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6.QtCore")


def _install_pipeline(monkeypatch: pytest.MonkeyPatch, func: Callable) -> None:
    monkeypatch.setattr(
        "localkoreantts.gui.workers.synth_worker.run_synthesis_pipeline",
        func,
    )


def test_worker_finishes(qtbot, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtCore import QThread  # type: ignore[import]
    from PySide6.QtTest import QSignalSpy  # type: ignore[import]

    from localkoreantts.gui.pipeline import SynthJobConfig  # type: ignore[import]
    from localkoreantts.gui.workers import SynthWorker  # type: ignore[import]

    def fake_pipeline(config: SynthJobConfig, hooks):
        hooks.on_stage("chunking")
        hooks.on_progress(1, 1)
        hooks.on_chunk_done(1, 1)
        time.sleep(0.01)
        return type("Result", (), {"output_path": tmp_path / "out.wav"})()

    _install_pipeline(monkeypatch, fake_pipeline)
    worker = SynthWorker(
        SynthJobConfig(
            job_id=1,
            text="hello",
            input_path=None,
            output_dir=tmp_path,
            output_format="wav",
            model_path=tmp_path,
            cache_dir=tmp_path,
            ffmpeg_bin="ffmpeg",
            speed=1.0,
            sample_rate=22_050,
            silence_milliseconds=0,
        )
    )
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    finished_spy = QSignalSpy(worker.finished)
    thread.start()
    qtbot.waitSignal(worker.finished, timeout=2000)
    thread.quit()
    qtbot.waitSignal(thread.finished, timeout=2000)
    assert finished_spy


def test_worker_cancel(qtbot, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtCore import QThread  # type: ignore[import]
    from PySide6.QtTest import QSignalSpy  # type: ignore[import]

    from localkoreantts.gui.pipeline import JobCancelled, SynthJobConfig  # type: ignore[import]
    from localkoreantts.gui.workers import SynthWorker  # type: ignore[import]

    def fake_pipeline(config: SynthJobConfig, hooks):
        hooks.on_stage("chunking")
        hooks.on_progress(1, 10)
        if hooks.should_cancel():
            raise JobCancelled()
        time.sleep(0.05)
        raise AssertionError("should cancel before completion")

    _install_pipeline(monkeypatch, fake_pipeline)
    worker = SynthWorker(
        SynthJobConfig(
            job_id=2,
            text="cancel",
            input_path=None,
            output_dir=tmp_path,
            output_format="wav",
            model_path=tmp_path,
            cache_dir=tmp_path,
            ffmpeg_bin="ffmpeg",
            speed=1.0,
            sample_rate=22_050,
            silence_milliseconds=0,
        )
    )
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    cancelled_spy = QSignalSpy(worker.cancelled)
    thread.start()
    qtbot.wait(50)
    worker.request_cancel()
    qtbot.waitSignal(worker.cancelled, timeout=2000)
    thread.quit()
    qtbot.waitSignal(thread.finished, timeout=2000)
    assert cancelled_spy
