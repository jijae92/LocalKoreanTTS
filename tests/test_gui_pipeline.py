"""Tests for the GUI synthesis pipeline utilities."""
from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import pytest

from localkoreantts.gui.pipeline import (
    JobCancelled,
    PipelineHooks,
    SynthJobConfig,
    run_synthesis_pipeline,
)


def _make_wav_bytes(sample_rate: int = 22_050, duration: float = 0.05) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = int(sample_rate * duration)
        wav_file.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


class DummyVITS:
    sample_rate = 22_050

    def generate_wav_bytes(self, text: str, speed: float) -> bytes:
        return _make_wav_bytes()


def _fake_concat(
    wav_paths: list[str], out_path: str, silence_duration: float, ffmpeg_bin: str
) -> None:
    Path(out_path).write_bytes(Path(wav_paths[0]).read_bytes())


@pytest.fixture(autouse=True)
def _patch_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "localkoreantts.gui.pipeline.create_local_vits",
        lambda model_path, sample_rate, ffmpeg_bin: DummyVITS(),
    )
    monkeypatch.setattr(
        "localkoreantts.gui.pipeline.utils.concat_wavs_with_silence",
        _fake_concat,
    )
    monkeypatch.setattr(
        "localkoreantts.gui.pipeline._transcode_audio",
        lambda source, target, fmt, ffmpeg_bin: Path(target).write_bytes(
            Path(source).read_bytes()
        ),
    )


def test_pipeline_generates_artifacts(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "artifacts"
    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(b"model")

    config = SynthJobConfig(
        job_id=1,
        text="안녕하세요. 테스트입니다.",
        input_path=None,
        output_dir=output_dir,
        output_format="wav",
        model_path=model_path,
        cache_dir=cache_dir,
        ffmpeg_bin="ffmpeg",
        speed=1.0,
        sample_rate=22_050,
        silence_milliseconds=0,
    )

    logs: list[str] = []
    progress: list[tuple[int, int]] = []
    stages: list[str] = []
    chunks: list[tuple[int, int]] = []
    hooks = PipelineHooks(
        should_cancel=lambda: False,
        on_progress=lambda done, total: progress.append((done, total)),
        on_log=lambda msg: logs.append(msg),
        on_stage=lambda stage: stages.append(stage),
        on_chunk_done=lambda done, total: chunks.append((done, total)),
    )

    result = run_synthesis_pipeline(config, hooks)

    assert result.output_path.exists()
    assert result.meta_path.exists()
    assert result.sha_path.exists()
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["chunks"] >= 1
    assert result.cache_hits == 0
    assert result.cache_misses == meta["chunks"]
    assert logs, "expected log entries"
    assert progress and progress[-1][0] == progress[-1][1]
    assert chunks and chunks[-1][0] == chunks[-1][1]
    assert any(stage == "completed" for stage in stages)

    # Second run should reuse cache
    second_result = run_synthesis_pipeline(config, hooks)
    assert second_result.cache_hits >= 1


def test_pipeline_cancel(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "artifacts"
    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(b"model")

    config = SynthJobConfig(
        job_id=2,
        text="반복 테스트" * 5,
        input_path=None,
        output_dir=output_dir,
        output_format="wav",
        model_path=model_path,
        cache_dir=cache_dir,
        ffmpeg_bin="ffmpeg",
        speed=1.0,
        sample_rate=22_050,
        silence_milliseconds=0,
    )

    counter = {"calls": 0}

    def should_cancel() -> bool:
        counter["calls"] += 1
        return counter["calls"] > 1

    stages: list[str] = []
    hooks = PipelineHooks(
        should_cancel=should_cancel,
        on_stage=lambda stage: stages.append(stage),
    )

    with pytest.raises(JobCancelled):
        run_synthesis_pipeline(config, hooks)
    assert "cancelled" in stages
