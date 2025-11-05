"""Command line interface for Local Korean TTS."""
from __future__ import annotations

import argparse
import hashlib
import logging
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from . import utils
from .cache import CacheManager, make_cache_key
from .pii import scrub
from .tts import DEFAULT_SAMPLE_RATE, DEFAULT_SPEED, LocalVITS

FORMAT_CHOICES = ("wav", "ogg", "mp3")
LOGGER = utils.get_logger()


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Local Korean TTS CLI")
    parser.add_argument(
        "--in",
        dest="input_path",
        type=Path,
        required=True,
        help="Input text or markdown file path",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        type=Path,
        required=True,
        help="Output audio file path",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED,
        help=f"Playback speed multiplier (default: {DEFAULT_SPEED})",
    )
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        default="wav",
        help="Output audio format (default: wav)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Cache directory (falls back to LK_TTS_CACHE_DIR)",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        help="Model path (falls back to LK_TTS_MODEL_PATH)",
    )
    parser.add_argument(
        "--silence",
        type=float,
        default=0.12,
        help="Silence padding (seconds) inserted between chunks (default: 0.12)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point returning an exit code."""
    try:
        return _run_cli(argv)
    except Exception as exc:  # pragma: no cover - defensive catch
        LOGGER.exception("CLI failed")
        sys.stderr.write(f"Error: {exc}\n")
        return 3


def _run_cli(argv: Sequence[str] | None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    log_level = _resolve_log_level(args.log_level)
    utils.configure_logging(level=log_level)
    LOGGER.setLevel(log_level)

    input_path = args.input_path
    output_path = args.output_path
    output_format = args.format
    silence = args.silence
    speed = args.speed
    if speed <= 0:
        raise ValueError("speed must be greater than zero.")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    text = input_path.read_text(encoding="utf-8")
    LOGGER.debug("Scrubbed preview", extra={"preview": scrub(text)[:160]})

    cache = CacheManager(cache_dir=args.cache_dir)

    model_path = utils.resolve_model_path(args.model_path)

    ffmpeg_bin = utils.resolve_ffmpeg_bin()
    sample_rate = int(
        utils.get_env_float("LK_TTS_SAMPLE_RATE", float(DEFAULT_SAMPLE_RATE))
    )
    local_vits = create_local_vits(
        model_path, sample_rate=sample_rate, ffmpeg_bin=ffmpeg_bin
    )
    effective_sample_rate = local_vits.sample_rate

    chunks = utils.chunk_text(text)
    if not chunks:
        raise ValueError("Input text produced no synthesis chunks.")

    chunk_paths: list[str] = []
    cache_hits = 0
    cache_misses = 0

    for chunk_index, chunk in enumerate(chunks):
        key = make_cache_key(
            model_path=str(model_path),
            text=chunk,
            speed=speed,
            sample_rate=effective_sample_rate,
            format="wav",
        )
        cached_path = cache.get_cached_path(key)
        if cached_path:
            cache_hits += 1
            LOGGER.debug(
                "Chunk cache hit",
                extra={"index": chunk_index, "path": cached_path},
            )
            chunk_paths.append(cached_path)
            continue

        wav_bytes = local_vits.generate_wav_bytes(chunk, speed=speed)
        metadata = {
            "model_path": str(model_path),
            "sample_rate": effective_sample_rate,
            "speed": speed,
            "format": "wav",
            "text_length": len(chunk),
        }
        stored_path = cache.store(key, wav_bytes, metadata)
        cache_misses += 1
        LOGGER.debug("Chunk cached", extra={"index": chunk_index, "path": stored_path})
        chunk_paths.append(stored_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_target = (
        output_path
        if output_format == "wav"
        else output_path.parent / f"{output_path.stem}_concat.wav"
    )

    utils.concat_wavs_with_silence(
        chunk_paths,
        str(concat_target),
        silence_duration=silence,
        ffmpeg_bin=ffmpeg_bin,
    )

    if output_format != "wav":
        _transcode_audio(concat_target, output_path, output_format, ffmpeg_bin)
        if concat_target.exists():
            concat_target.unlink()

    final_path = output_path
    sha256_hex = _compute_sha256(final_path)

    metadata_path = Path(f"{final_path}.meta.json")
    meta = {
        "input": str(input_path),
        "output": str(final_path),
        "format": output_format,
        "speed": speed,
        "sample_rate": effective_sample_rate,
        "chunks": len(chunks),
        "silence_duration": silence,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_dir": str(cache.base_dir),
        "model_path": str(model_path),
        "sha256": sha256_hex,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    utils.atomic_write_text(metadata_path, utils.json_dump(meta))

    LOGGER.info(
        "Synthesis complete",
        extra={
            "output": str(final_path),
            "chunks": len(chunks),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        },
    )
    return 0


def _resolve_log_level(value: str) -> int:
    candidate = value.upper()
    level = getattr(logging, candidate, None)
    if isinstance(level, int):
        return level
    LOGGER.warning("Unknown log level '%s', defaulting to INFO", value)
    return logging.INFO


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _transcode_audio(source: Path, target: Path, fmt: str, ffmpeg_bin: str) -> None:
    codec_map = {
        "mp3": "libmp3lame",
        "ogg": "libvorbis",
    }
    codec = codec_map.get(fmt, "pcm_s16le")
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-c:a",
        codec,
        str(target),
    ]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:  # pragma: no cover - requires ffmpeg
        raise RuntimeError("ffmpeg executable not found.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffmpeg command failed: {' '.join(command)}") from exc


def create_local_vits(
    model_path: Path | str, *, sample_rate: int, ffmpeg_bin: str
) -> LocalVITS:
    """Factory for LocalVITS allowing tests to inject fakes."""
    return LocalVITS(str(model_path), sample_rate=sample_rate, ffmpeg_bin=ffmpeg_bin)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
