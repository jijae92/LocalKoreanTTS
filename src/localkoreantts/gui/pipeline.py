"""Shared synthesis pipeline used by the GUI worker."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

from .. import pii, utils
from ..cache import CacheManager, make_cache_key
from ..cli import _compute_sha256, _transcode_audio, create_local_vits


class JobCancelled(Exception):
    """Raised when a synthesis job is cancelled."""


@dataclass(frozen=True)
class SynthJobConfig:
    """Configuration for a synthesis pipeline execution."""

    job_id: int
    text: str
    input_path: Path | None
    output_dir: Path
    output_format: str
    model_path: Path
    cache_dir: Path
    ffmpeg_bin: str
    speed: float
    sample_rate: int
    silence_milliseconds: int


@dataclass(frozen=True)
class PipelineHooks:
    """Lifecycle hooks for pipeline progress and cancellation."""

    should_cancel: Callable[[], bool] = lambda: False
    on_progress: Callable[[int, int], None] = lambda *_: None
    on_log: Callable[[str], None] = lambda _msg: None
    on_stage: Callable[[str], None] = lambda _stage: None
    on_chunk_done: Callable[[int, int], None] = lambda *_: None


@dataclass(frozen=True)
class SynthResult:
    """Outcome of the synthesis pipeline."""

    output_path: Path
    meta_path: Path
    sha_path: Path
    chunk_count: int
    cache_hits: int
    cache_misses: int
    effective_sample_rate: int


def run_synthesis_pipeline(
    config: SynthJobConfig,
    hooks: PipelineHooks | None = None,
) -> SynthResult:
    """Run the synthesis pipeline mirroring CLI logic."""
    hooks = hooks or PipelineHooks()

    def _check_cancel() -> None:
        if hooks.should_cancel():
            raise JobCancelled()

    cleanup_paths: list[Path] = []

    hooks.on_stage("loading_input")
    text = config.text
    if not text and config.input_path:
        text = config.input_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("합성할 텍스트가 비어 있습니다.")

    hooks.on_log(f"입력 길이: {len(text)} chars")
    hooks.on_log(f"입력 미리보기: {pii.scrub(text)[:160]}")
    hooks.on_stage("chunking")

    chunks = utils.chunk_text(text)
    if not chunks:
        raise ValueError("청크를 생성할 수 없습니다.")
    hooks.on_log(f"{len(chunks)}개의 청크 생성")

    cache_manager = CacheManager(cache_dir=config.cache_dir)
    chunk_paths: list[str] = []
    cache_hits = 0
    cache_misses = 0
    local_vits = None
    effective_sample_rate = config.sample_rate

    _check_cancel()

    try:
        for index, chunk in enumerate(chunks, start=1):
            _check_cancel()
            cache_key = make_cache_key(
                model_path=str(config.model_path),
                text=chunk,
                speed=config.speed,
                sample_rate=config.sample_rate,
                format="wav",
            )
            cached_path = cache_manager.get_cached_path(cache_key)
            hooks.on_stage("chunk_cache_check")
            if cached_path:
                cache_hits += 1
                hooks.on_log(f"청크 {index}/{len(chunks)}: cache HIT")
                chunk_paths.append(cached_path)
            else:
                if local_vits is None:
                    hooks.on_stage("loading_model")
                    local_vits = create_local_vits(
                        config.model_path,
                        sample_rate=config.sample_rate,
                        ffmpeg_bin=config.ffmpeg_bin,
                    )
                    effective_sample_rate = local_vits.sample_rate
                    hooks.on_log(
                        f"모델 로드 완료 (sample_rate={effective_sample_rate})",
                    )
                hooks.on_log(f"청크 {index}/{len(chunks)}: cache MISS → 합성")
                hooks.on_stage("chunk_synth")
                attempts = 0
                while True:
                    try:
                        _check_cancel()
                        wav_bytes = local_vits.generate_wav_bytes(
                            chunk, speed=config.speed
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        attempts += 1
                        hooks.on_log(f"청크 합성 실패: {exc!s}")
                        if attempts > 1:
                            raise
                        hooks.on_stage("chunk_retry")
                        sleep(0.5)
                        continue
                    break
                metadata = {
                    "model_path": str(config.model_path),
                    "sample_rate": effective_sample_rate,
                    "speed": config.speed,
                    "format": "wav",
                    "text_length": len(chunk),
                }
                chunk_path = cache_manager.store(cache_key, wav_bytes, metadata)
                cache_misses += 1
                chunk_paths.append(chunk_path)

            hooks.on_progress(index, len(chunks))
            hooks.on_chunk_done(index, len(chunks))

        _check_cancel()

        hooks.on_stage("preparing_output")
        utils.ensure_directory(config.output_dir)
        base_name = _derive_output_name(config)
        output_format = config.output_format.lower()
        if output_format not in {"wav", "ogg", "mp3"}:
            raise ValueError(f"지원하지 않는 포맷: {output_format}")

        final_path = config.output_dir / f"{base_name}.{output_format}"
        concat_target = (
            final_path
            if output_format == "wav"
            else config.output_dir / f"{base_name}_concat.wav"
        )

        hooks.on_stage("concatenating")
        utils.concat_wavs_with_silence(
            chunk_paths,
            str(concat_target),
            silence_duration=config.silence_milliseconds / 1000.0,
            ffmpeg_bin=config.ffmpeg_bin,
        )

        if output_format != "wav":
            _check_cancel()
            _transcode_audio(
                concat_target, final_path, output_format, config.ffmpeg_bin
            )
            if concat_target.exists():
                concat_target.unlink()
        else:
            final_path = concat_target

        cleanup_paths.append(final_path)
        _check_cancel()

        hooks.on_stage("finalising")
        sha256_hex = _compute_sha256(final_path)
        metadata_path = Path(f"{final_path}.meta.json")
        cleanup_paths.append(metadata_path)
        meta = {
            "output": str(final_path),
            "format": output_format,
            "speed": config.speed,
            "sample_rate": effective_sample_rate,
            "chunks": len(chunks),
            "silence_duration": config.silence_milliseconds / 1000.0,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_dir": str(cache_manager.base_dir),
            "model_path": str(config.model_path),
            "sha256": sha256_hex,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        utils.atomic_write_text(metadata_path, utils.json_dump(meta))

        sha_path = final_path.with_suffix(f"{final_path.suffix}.sha256")
        cleanup_paths.append(sha_path)
        utils.atomic_write_text(sha_path, sha256_hex)

        hooks.on_log(f"결과 파일: {final_path}")
        hooks.on_stage("completed")

        return SynthResult(
            output_path=final_path,
            meta_path=metadata_path,
            sha_path=sha_path,
            chunk_count=len(chunks),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            effective_sample_rate=effective_sample_rate,
        )
    except JobCancelled:
        hooks.on_stage("cancelled")
        _cleanup_paths(cleanup_paths)
        raise
    except Exception:
        hooks.on_stage("error")
        _cleanup_paths(cleanup_paths)
        raise


def _derive_output_name(config: SynthJobConfig) -> str:
    if config.input_path and config.input_path.stem:
        stem = config.input_path.stem
    else:
        stem = f"text_{config.job_id:04d}"
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}"


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:  # pragma: no cover - best effort cleanup
            utils.LOGGER.debug("Failed to cleanup path", extra={"path": str(path)})
