"""Tests for the CLI interface."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import subprocess
import wave
from pathlib import Path

import pytest

from localkoreantts import cli


def _build_wav_bytes(*, sample_rate: int, duration: float) -> bytes:
    buffer = io.BytesIO()
    frames = int(sample_rate * duration)
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)
    return buffer.getvalue()


def _sample_file() -> Path:
    return Path(__file__).resolve().parent.parent / "sample" / "sample.txt"


class RecordingVITS:
    def __init__(self, sample_rate: int = 8_000) -> None:
        self.sample_rate = sample_rate
        self.calls: int = 0
        self._payload = _build_wav_bytes(sample_rate=sample_rate, duration=0.05)

    def generate_wav_bytes(self, text: str, speed: float = 1.0) -> bytes:
        self.calls += 1
        return self._payload


def test_cli_creates_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / "cache"
    output_path = tmp_path / "out.wav"

    monkeypatch.setattr(
        "localkoreantts.utils.chunk_text",
        lambda text, max_chars=3500, prefer_sentence_boundary=True, overlap_chars=40: [
            text
        ],
    )

    dummy = RecordingVITS()
    monkeypatch.setattr(
        "localkoreantts.cli.create_local_vits",
        lambda model_path, sample_rate, ffmpeg_bin: dummy,
    )
    monkeypatch.setenv("LK_TTS_SAMPLE_RATE", "8000")

    exit_code = cli.main(
        [
            "--in",
            str(_sample_file()),
            "--out",
            str(output_path),
            "--cache-dir",
            str(cache_dir),
            "--model-path",
            "dummy-model",
            "--silence",
            "0.0",
            "--log-level",
            "DEBUG",
            "--format",
            "wav",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()

    meta_path = Path(f"{output_path}.meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["chunks"] == 1
    assert meta["cache_hits"] == 0
    assert meta["cache_misses"] == 1
    assert dummy.calls == 1


def test_cache_hit_uses_cached_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    output_path = tmp_path / "out.wav"

    monkeypatch.setattr(
        "localkoreantts.utils.chunk_text",
        lambda text, max_chars=3500, prefer_sentence_boundary=True, overlap_chars=40: [
            text
        ],
    )

    dummy = RecordingVITS()
    monkeypatch.setattr(
        "localkoreantts.cli.create_local_vits",
        lambda *args, **kwargs: dummy,
    )
    monkeypatch.setenv("LK_TTS_SAMPLE_RATE", "8000")

    first_exit = cli.main(
        [
            "--in",
            str(_sample_file()),
            "--out",
            str(output_path),
            "--cache-dir",
            str(cache_dir),
            "--model-path",
            "dummy-model",
            "--silence",
            "0.0",
            "--format",
            "wav",
        ]
    )
    assert first_exit == 0
    first_calls = dummy.calls

    second_exit = cli.main(
        [
            "--in",
            str(_sample_file()),
            "--out",
            str(output_path),
            "--cache-dir",
            str(cache_dir),
            "--model-path",
            "dummy-model",
            "--silence",
            "0.0",
            "--format",
            "wav",
        ]
    )
    assert second_exit == 0
    assert dummy.calls == first_calls

    meta_path = Path(f"{output_path}.meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["cache_hits"] == 1
    assert meta["cache_misses"] == 0


def test_cli_mp3_transcode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    output_path = tmp_path / "out.mp3"

    monkeypatch.setattr(
        "localkoreantts.utils.chunk_text",
        lambda text, max_chars=3500, prefer_sentence_boundary=True, overlap_chars=40: [
            text
        ],
    )

    dummy = RecordingVITS()
    monkeypatch.setattr(
        "localkoreantts.cli.create_local_vits",
        lambda *args, **kwargs: dummy,
    )

    intermediate_files: list[Path] = []

    def fake_concat(
        wavs: list[str],
        out_path: str,
        silence_duration: float,
        ffmpeg_bin: str,
    ) -> None:
        concat = Path(out_path)
        concat.write_bytes(
            _build_wav_bytes(sample_rate=dummy.sample_rate, duration=0.1)
        )
        intermediate_files.append(concat)

    monkeypatch.setattr(
        "localkoreantts.utils.concat_wavs_with_silence",
        fake_concat,
    )

    transcode_calls: list[tuple[Path, Path, str]] = []

    def fake_transcode(
        source: Path, target: Path, fmt: str, ffmpeg_bin: str
    ) -> None:
        transcode_calls.append((source, target, fmt))
        target.write_bytes(b"ID3data")

    monkeypatch.setattr("localkoreantts.cli._transcode_audio", fake_transcode)
    monkeypatch.setattr("localkoreantts.cli._compute_sha256", lambda path: "hash")

    exit_code = cli.main(
        [
            "--in",
            str(_sample_file()),
            "--out",
            str(output_path),
            "--cache-dir",
            str(cache_dir),
            "--model-path",
            "dummy-model",
            "--silence",
            "0.1",
            "--format",
            "mp3",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
    assert transcode_calls and transcode_calls[0][2] == "mp3"
    assert intermediate_files and not intermediate_files[0].exists()
    meta = json.loads(Path(f"{output_path}.meta.json").read_text(encoding="utf-8"))
    assert meta["format"] == "mp3"
    assert meta["sha256"] == "hash"


def test_cli_invalid_speed_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    exit_code = cli.main(
        [
            "--in",
            str(_sample_file()),
            "--out",
            str(tmp_path / "out.wav"),
            "--cache-dir",
            str(cache_dir),
            "--model-path",
            "dummy-model",
            "--speed",
            "-1",
        ]
    )
    assert exit_code == 3


def test_cli_missing_input_returns_error(tmp_path: Path) -> None:
    output_path = tmp_path / "out.wav"
    exit_code = cli.main(
        [
            "--in",
            str(tmp_path / "missing.txt"),
            "--out",
            str(output_path),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )
    assert exit_code == 3


def test_cli_empty_chunks_raise_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("   ", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    def no_chunks(
        text: str,
        max_chars: int = 3500,
        prefer_sentence_boundary: bool = True,
        overlap_chars: int = 40,
    ) -> list[str]:
        return []

    monkeypatch.setattr("localkoreantts.utils.chunk_text", no_chunks)
    dummy = RecordingVITS()
    monkeypatch.setattr(
        "localkoreantts.cli.create_local_vits",
        lambda *args, **kwargs: dummy,
    )

    exit_code = cli.main(
        [
            "--in",
            str(sample),
            "--out",
            str(tmp_path / "out.wav"),
            "--cache-dir",
            str(cache_dir),
            "--model-path",
            "dummy-model",
        ]
    )
    assert exit_code == 3


def test_transcode_audio_invokes_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        commands.append(cmd)
        (tmp_path / "target.mp3").write_bytes(b"ID3")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("localkoreantts.cli.subprocess.run", fake_run)
    source = tmp_path / "source.wav"
    source.write_bytes(b"RIFFdata")
    target = tmp_path / "target.mp3"
    cli._transcode_audio(source, target, "mp3", "ffmpeg")
    assert target.exists()
    assert commands and commands[0][0] == "ffmpeg"


def test_transcode_audio_missing_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        raise FileNotFoundError

    monkeypatch.setattr("localkoreantts.cli.subprocess.run", fake_run)
    with pytest.raises(RuntimeError):
        cli._transcode_audio(tmp_path / "s.wav", tmp_path / "t.mp3", "mp3", "ffmpeg")


def test_transcode_audio_failure_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd, check):  # type: ignore[no-untyped-def]
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr("localkoreantts.cli.subprocess.run", fake_run)
    with pytest.raises(RuntimeError):
        cli._transcode_audio(tmp_path / "s.wav", tmp_path / "t.mp3", "mp3", "ffmpeg")


def test_resolve_log_level_unknown_defaults() -> None:
    assert cli._resolve_log_level("not-a-level") == logging.INFO


def test_resolve_log_level_known() -> None:
    assert cli._resolve_log_level("debug") == logging.DEBUG


def test_compute_sha256(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    data = b"hello"
    path.write_bytes(data)
    assert cli._compute_sha256(path) == hashlib.sha256(data).hexdigest()


def test_create_local_vits_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    class Dummy:
        def __init__(self, model_path: str, sample_rate: int, ffmpeg_bin: str) -> None:
            recorded["model_path"] = model_path
            recorded["sample_rate"] = sample_rate
            recorded["ffmpeg_bin"] = ffmpeg_bin

    monkeypatch.setattr("localkoreantts.cli.LocalVITS", Dummy)
    result = cli.create_local_vits("model", sample_rate=22_050, ffmpeg_bin="ffmpeg")
    assert isinstance(result, Dummy)
    assert recorded == {
        "model_path": "model",
        "sample_rate": 22_050,
        "ffmpeg_bin": "ffmpeg",
    }
