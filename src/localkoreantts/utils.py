"""Utility helpers for Local Korean TTS."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from .pii import scrub

PACKAGE_NAME = "localkoreantts"
STANDARD_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class PIIScrubFilter(logging.Filter):
    """Log filter that masks PII using :func:`localkoreantts.pii.scrub`."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        if record.args:
            record.args = tuple(
                scrub(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        for key, value in list(record.__dict__.items()):
            if key in STANDARD_LOG_RECORD_ATTRS:
                continue
            if isinstance(value, str):
                setattr(record, key, scrub(value))
        return True


def _ensure_pii_filter(logger: logging.Logger) -> logging.Logger:
    """Attach PIIScrubFilter to *logger* if not already present."""
    if all(not isinstance(filt, PIIScrubFilter) for filt in logger.filters):
        logger.addFilter(PIIScrubFilter())
    return logger


def get_logger() -> logging.Logger:
    """Return the package logger with the PII filter installed."""
    return _ensure_pii_filter(logging.getLogger(PACKAGE_NAME))


LOGGER = get_logger()


def configure_logging(verbose: bool = False, *, level: int | None = None) -> None:
    """Configure the package-wide logger.

    Parameters
    ----------
    verbose:
        When ``True`` the global logger emits DEBUG level messages. Otherwise INFO.
    level:
        Optional explicit logging level overriding ``verbose``.
    """
    target_level = level if level is not None else (
        logging.DEBUG if verbose else logging.INFO
    )
    logging.basicConfig(
        level=target_level,
        format="%(levelname)s %(name)s: %(message)s",
    )
    base_logger = get_logger()
    base_logger.setLevel(target_level)
    base_logger.debug(
        "Logger configured", extra={"verbose": verbose, "level": target_level}
    )


def get_env_path(name: str, default: str | Path) -> Path:
    """Return a POSIX path from an environment variable or default."""
    value = os.getenv(name, default)
    path = Path(value).expanduser().resolve()
    LOGGER.debug("Resolved path env", extra={"env_var": name, "path": str(path)})
    return path


def get_env_str(name: str, default: str) -> str:
    """Return a sanitized string environment variable value."""
    value = os.getenv(name, default).strip()
    LOGGER.debug("Resolved str env", extra={"env_var": name})
    return value


def get_env_float(name: str, default: float) -> float:
    """Return a float environment variable value with fallback."""
    raw_value = os.getenv(name)
    if raw_value is None:
        LOGGER.debug("No float env override", extra={"env_var": name})
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Environment variable {name} must be a float") from exc
    LOGGER.debug("Resolved float env", extra={"env_var": name, "value": value})
    return value


def _user_cache_root() -> Path:
    return Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))


def _user_data_root() -> Path:
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def default_cache_dir() -> Path:
    """Return the default cache directory."""
    configured = os.getenv("LK_TTS_CACHE_DIR")
    if configured:
        resolved = Path(configured).expanduser().resolve()
        LOGGER.debug("Using configured cache dir", extra={"path": str(resolved)})
        return resolved
    path = (_user_cache_root() / PACKAGE_NAME).resolve()
    LOGGER.debug("Derived cache dir", extra={"path": str(path)})
    return path


def default_model_path() -> Path:
    """Return the default model path."""
    configured = os.getenv("LK_TTS_MODEL_PATH")
    if configured:
        resolved = Path(configured).expanduser().resolve()
        LOGGER.debug("Using configured model path", extra={"path": str(resolved)})
        return resolved
    path = (_user_data_root() / PACKAGE_NAME / "model").resolve()
    LOGGER.debug("Derived model path", extra={"path": str(path)})
    return path


def resolve_cache_dir(candidate: Path | str | None) -> Path:
    """Resolve the cache directory honoring explicit and environment overrides."""
    if candidate is not None:
        resolved = Path(candidate).expanduser().resolve()
        LOGGER.debug("Using explicit cache dir", extra={"path": str(resolved)})
        return resolved
    return default_cache_dir()


def resolve_model_path(candidate: Path | str | None) -> Path:
    """Resolve the model path honoring explicit and environment overrides."""
    if candidate is not None:
        resolved = Path(candidate).expanduser().resolve()
        LOGGER.debug("Using explicit model path", extra={"path": str(resolved)})
        return resolved
    return default_model_path()


def resolve_ffmpeg_bin(candidate: str | None = None) -> str:
    """Resolve the ffmpeg binary path honouring overrides and PATH discovery."""
    if candidate:
        LOGGER.debug("Using explicit ffmpeg binary", extra={"path": candidate})
        return candidate
    configured = os.getenv("LK_TTS_FFMPEG_BIN")
    if configured:
        LOGGER.debug("Using configured ffmpeg binary", extra={"path": configured})
        return configured.strip()
    discovered = shutil.which("ffmpeg")
    if discovered:
        LOGGER.debug("Discovered ffmpeg binary", extra={"path": discovered})
        return discovered
    LOGGER.debug("Defaulting to ffmpeg on PATH")
    return "ffmpeg"


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Persist binary payload atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as tmp_file:
        tmp_file.write(payload)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_name = Path(tmp_file.name)
    os.replace(tmp_name, path)
    dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Persist textual payload atomically."""
    atomic_write_bytes(path, text.encode(encoding))


def ensure_directory(path: Path) -> Path:
    """Ensure that a directory exists and return its path."""
    path.mkdir(parents=True, exist_ok=True)
    LOGGER.debug("Ensured directory", extra={"path": str(path)})
    return path


def read_text_source(text: str | None, input_path: Path | None) -> str:
    """Return text either from a literal argument or a file path."""
    if text and input_path:
        raise ValueError("Provide either `text` or `input_path`, not both.")
    if text:
        return text
    if input_path:
        content = input_path.read_text(encoding="utf-8")
        LOGGER.debug(
            "Loaded input text", extra={"bytes": len(content.encode("utf-8"))}
        )
        return content
    raise ValueError("Either `text` or `input_path` must be provided.")


def json_dump(data: Any) -> str:
    """Return a JSON payload with consistent formatting."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def chunk_text(
    text: str,
    max_chars: int = 3500,
    *,
    prefer_sentence_boundary: bool = True,
    overlap_chars: int = 40,
) -> list[str]:
    """Split text into overlapping chunks respecting sentence boundaries."""

    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be zero or positive.")
    if not text:
        return []

    effective_overlap = 0
    if max_chars > 1 and overlap_chars:
        effective_overlap = min(overlap_chars, max_chars // 2 or 1)

    tokens = _tokenize_text(text, prefer_sentence_boundary)

    chunks: list[str] = []
    current: str = ""
    has_new_content = False

    def start_new_chunk() -> None:
        nonlocal current, has_new_content
        if current:
            chunks.append(current)
        current = ""
        has_new_content = False

    def rollover_with_overlap() -> None:
        nonlocal current, has_new_content
        tail = current[-effective_overlap:] if effective_overlap and current else ""
        start_new_chunk()
        current = tail
        has_new_content = False

    for token in tokens:
        remaining = token
        if not remaining:
            continue
        if (
            len(remaining) <= max_chars
            and current
            and len(current) + len(remaining) > max_chars
        ):
            rollover_with_overlap()
        while remaining:
            available = max_chars - len(current)
            if available <= 0:
                rollover_with_overlap()
                available = max_chars - len(current)
                if available <= 0:
                    current = current[-max_chars:]
                    available = max_chars - len(current)
            take = min(len(remaining), available if available > 0 else len(remaining))
            if take == 0:
                start_new_chunk()
                continue
            current += remaining[:take]
            has_new_content = True
            remaining = remaining[take:]
            if len(current) >= max_chars:
                rollover_with_overlap()

    if current and has_new_content:
        chunks.append(current)

    return chunks


def _tokenize_text(text: str, prefer_sentence_boundary: bool) -> list[str]:
    segments = _split_markdown_segments(text)
    tokens: list[str] = []
    for segment, is_code_block in segments:
        if is_code_block:
            tokens.append(segment)
        elif prefer_sentence_boundary:
            tokens.extend(_split_sentences(segment))
        else:
            tokens.append(segment)
    return tokens if tokens else [text]


def _split_markdown_segments(text: str) -> list[tuple[str, bool]]:
    segments: list[tuple[str, bool]] = []
    buffer: list[str] = []
    in_code = False

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if in_code:
                buffer.append(line)
                segments.append(("".join(buffer), True))
                buffer = []
                in_code = False
            else:
                if buffer:
                    segments.append(("".join(buffer), False))
                    buffer = []
                buffer.append(line)
                in_code = True
            continue

        buffer.append(line)

    if buffer:
        segments.append(("".join(buffer), in_code))

    return segments or [(text, False)]


def _split_sentences(segment: str) -> list[str]:
    if not segment:
        return []

    sentences: list[str] = []
    start = 0
    length = len(segment)
    i = 0

    while i < length:
        char = segment[i]

        if char in ".!?":
            i += 1
            while i < length and segment[i].isspace():
                if segment[i] == "\n":
                    newline_start = i
                    while i < length and segment[i] == "\n":
                        i += 1
                    if i - newline_start >= 2:
                        break
                    continue
                i += 1
            sentences.append(segment[start:i])
            start = i
            continue

        if char == "\n":
            newline_start = i
            while i < length and segment[i] == "\n":
                i += 1
            if i - newline_start >= 2:
                sentences.append(segment[start:i])
                start = i
            continue

        i += 1

    if start < length:
        sentences.append(segment[start:])

    return [sentence for sentence in sentences if sentence]


def concat_wavs_with_silence(
    wav_paths: list[str],
    out_path: str,
    silence_duration: float = 0.12,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    """Concatenate WAV files inserting silence between each chunk via FFmpeg."""

    if not wav_paths:
        raise ValueError("wav_paths must not be empty.")
    resolved_inputs = [Path(path).resolve() for path in wav_paths]
    for path in resolved_inputs:
        if not path.exists():
            raise FileNotFoundError(f"Input WAV not found: {path}")

    reference_channels, reference_rate, reference_width = _inspect_wav(
        resolved_inputs[0]
    )
    for path in resolved_inputs[1:]:
        channels, rate, width = _inspect_wav(path)
        if (
            channels != reference_channels
            or rate != reference_rate
            or width != reference_width
        ):
            raise ValueError(
                "All inputs must share channel count, sample rate, and sample width."
            )

    out_path_obj = Path(out_path)
    out_path_obj.parent.mkdir(parents=True, exist_ok=True)

    if len(resolved_inputs) == 1 and silence_duration <= 0:
        shutil.copyfile(resolved_inputs[0], out_path_obj)
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        silence_path: Path | None = None
        if len(resolved_inputs) > 1 and silence_duration > 0:
            silence_path = Path(tmp_dir) / "silence.wav"
            _generate_silence_wav(
                silence_path,
                duration=silence_duration,
                sample_rate=reference_rate,
                channels=reference_channels,
                ffmpeg_bin=ffmpeg_bin,
            )

        concat_inputs: list[Path] = []
        for index, wav_path in enumerate(resolved_inputs):
            concat_inputs.append(wav_path)
            if silence_path and index < len(resolved_inputs) - 1:
                concat_inputs.append(silence_path)

        fd, tmp_name = tempfile.mkstemp(dir=str(out_path_obj.parent), suffix=".wav")
        os.close(fd)
        tmp_output = Path(tmp_name)
        try:
            _run_ffmpeg_concat(
                concat_inputs,
                tmp_output,
                sample_rate=reference_rate,
                channels=reference_channels,
                ffmpeg_bin=ffmpeg_bin,
            )
            os.replace(tmp_output, out_path_obj)
        finally:
            if tmp_output.exists():
                tmp_output.unlink()


def _run_ffmpeg_concat(
    inputs: list[Path],
    output_path: Path,
    *,
    sample_rate: int,
    channels: int,
    ffmpeg_bin: str,
) -> None:
    filters = "".join(f"[{idx}:a]" for idx in range(len(inputs)))
    filter_complex = f"{filters}concat=n={len(inputs)}:v=0:a=1[aout]"

    command = [ffmpeg_bin, "-hide_banner", "-loglevel", "error"]
    for input_path in inputs:
        command.extend(["-i", str(input_path)])
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[aout]",
            "-c",
            "pcm_s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-y",
            str(output_path),
        ]
    )
    _run_ffmpeg(command)


def _generate_silence_wav(
    silence_path: Path,
    *,
    duration: float,
    sample_rate: int,
    channels: int,
    ffmpeg_bin: str,
) -> None:
    layout = "mono" if channels == 1 else "stereo" if channels == 2 else f"{channels}c"
    lavfi_expr = f"anullsrc=r={sample_rate}:"
    if layout in {"mono", "stereo"}:
        lavfi_expr += f"cl={layout}"
    else:
        lavfi_expr += f"channel_layout={layout}"
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        lavfi_expr,
        "-t",
        f"{duration:.6f}",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c",
        "pcm_s16le",
        "-y",
        str(silence_path),
    ]
    _run_ffmpeg(command)


def _run_ffmpeg(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:  # pragma: no cover - requires FFmpeg presence
        raise RuntimeError("ffmpeg executable not found.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg command failed: {' '.join(command)}"
        ) from exc


def _inspect_wav(path: Path) -> tuple[int, int, int]:
    with wave.open(str(path), "rb") as wav_file:
        return (
            wav_file.getnchannels(),
            wav_file.getframerate(),
            wav_file.getsampwidth(),
        )
