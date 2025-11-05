"""Core synthesis engine for Local Korean TTS."""
from __future__ import annotations

import io
import wave
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from . import utils
from .cache import CacheManager, make_cache_key
from .pii import scrub

DEFAULT_MODEL_PATH = str(utils.default_model_path())
DEFAULT_SAMPLE_RATE = 22_050
DEFAULT_SPEED = 1.0
DEFAULT_VOICE = "standard"

try:  # pragma: no cover - optional dependency
    from TTS.api import TTS as _CoquiTTS  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    _CoquiTTS = None


@runtime_checkable
class ModelHandle(Protocol):
    """Protocol describing the minimal interface required from the VITS model."""

    sample_rate: int | None

    def synthesize(self, text: str, speed: float) -> Any:
        """Return either float numpy array data or raw WAV bytes."""


class _CoquiModelAdapter:
    """Thin wrapper translating the Coqui TTS API to the ModelHandle protocol."""

    def __init__(self, model: Any) -> None:
        self._model = model
        self.sample_rate = getattr(model, "sample_rate", None)

    def synthesize(self, text: str, speed: float) -> Any:
        return self._model.tts(text=text, speed=speed)


def _ensure_coqui_dir(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"LK_TTS_MODEL_PATH must be a directory, got: {p}")
    if not (p / "config.json").exists():
        raise FileNotFoundError(f"config.json not found under {p}")
    # 가중치 후보: *.pth / *.pt
    ckpts = list(p.glob("*.pth")) + list(p.glob("*.pt"))
    if not ckpts:
        raise FileNotFoundError(f"No checkpoint (*.pth|*.pt) under {p}")
    return p


def load_model(model_path: str) -> ModelHandle:
    """Load a Coqui TTS VITS model and return a compatible handle."""
    if _CoquiTTS is None:
        raise RuntimeError(
            "Coqui TTS package is not installed. Install it via `pip install TTS`."
        )
    model_dir = _ensure_coqui_dir(model_path)
    utils.LOGGER.info("Loading Coqui VITS model", extra={"model_path": str(model_dir)})
    model = _CoquiTTS(model_path=str(model_dir))
    return _CoquiModelAdapter(model)


class LocalVITS:
    """Lightweight wrapper around a Coqui VITS model that emits WAV files."""

    def __init__(
        self,
        model_path: str,
        sample_rate: int = 22_050,
        ffmpeg_bin: str | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be a positive integer.")
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._ffmpeg_bin = utils.resolve_ffmpeg_bin(ffmpeg_bin)
        self._model = load_model(model_path)
        model_sample_rate = getattr(self._model, "sample_rate", None)
        if isinstance(model_sample_rate, int | float):
            self._sample_rate = int(model_sample_rate)
        utils.LOGGER.debug(
            "LocalVITS initialised",
            extra={
                "model_path": model_path,
                "sample_rate": self._sample_rate,
                "ffmpeg_bin": ffmpeg_bin,
            },
        )

    @property
    def model_path(self) -> str:
        """Return the configured model path."""
        return self._model_path

    @property
    def sample_rate(self) -> int:
        """Return the effective sample rate."""
        return self._sample_rate

    @property
    def ffmpeg_bin(self) -> str:
        """Return the configured ffmpeg executable name/path."""
        return self._ffmpeg_bin

    def synthesize_to_wav(self, text: str, out_path: str, speed: float = 1.0) -> None:
        """Synthesize text and persist the WAV bytes to ``out_path``."""
        if speed <= 0:
            raise ValueError("speed must be greater than zero.")
        wav_bytes = self.generate_wav_bytes(text=text, speed=speed)
        output_path = Path(out_path)
        utils.atomic_write_bytes(output_path, wav_bytes)
        utils.LOGGER.info(
            "Wrote synthesized audio",
            extra={
                "out_path": str(output_path),
                "sample_rate": self._sample_rate,
                "bytes": len(wav_bytes),
            },
        )

    def generate_wav_bytes(self, text: str, speed: float = 1.0) -> bytes:
        """Return synthesized audio as WAV bytes."""
        if not text.strip():
            raise ValueError("text must not be empty.")
        if speed <= 0:
            raise ValueError("speed must be greater than zero.")
        raw_audio = self._model.synthesize(text=text, speed=speed)
        if isinstance(raw_audio, bytes):
            utils.LOGGER.debug("Model returned raw WAV bytes")
            return raw_audio
        return self._encode_samples(raw_audio)

    def _encode_samples(self, samples: Any) -> bytes:
        """Convert sequence-like samples to 16-bit PCM WAV bytes."""

        def _flatten(values: Any) -> list[float]:
            if hasattr(values, "tolist"):
                values = values.tolist()
            if isinstance(values, bytes | bytearray):
                raise RuntimeError("Expected numeric samples, not raw bytes.")
            if isinstance(values, list | tuple):
                flattened: list[float] = []
                for item in values:
                    flattened.extend(_flatten(item))
                return flattened
            try:
                return [float(values)]
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    "Unsupported audio sample type for encoding."
                ) from exc  # pragma: no cover - defensive branch

        flat_samples = _flatten(samples)
        if not flat_samples:
            raise RuntimeError("No audio samples provided for encoding.")

        pcm_bytes = bytearray()
        for sample in flat_samples:
            clamped = max(min(float(sample), 1.0), -1.0)
            int_sample = int(clamped * 32767.0)
            pcm_bytes.extend(int_sample.to_bytes(2, byteorder="little", signed=True))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(bytes(pcm_bytes))
        wav_bytes = buffer.getvalue()
        utils.LOGGER.debug("Encoded samples into WAV", extra={"bytes": len(wav_bytes)})
        return wav_bytes


@dataclass(frozen=True)
class SynthesisRequest:
    """Inputs required to create a synthesized utterance."""

    text: str
    voice: str = DEFAULT_VOICE
    sample_rate: int | None = None
    speed: float | None = None
    output_path: Path | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class SynthesisResult:
    """Resulting artefact for a synthesis request."""

    request: SynthesisRequest
    output_path: Path
    from_cache: bool


class TextToSpeechEngine:
    """High-level driver that orchestrates synthesis and caching."""

    def __init__(self, cache: CacheManager | None = None) -> None:
        self._cache = cache or CacheManager()
        self._model_path = utils.resolve_model_path(None)
        self._ffmpeg_bin = utils.resolve_ffmpeg_bin()
        self._default_sample_rate = int(
            utils.get_env_float("LK_TTS_SAMPLE_RATE", float(DEFAULT_SAMPLE_RATE))
        )
        self._default_speed = utils.get_env_float("LK_TTS_SPEED", DEFAULT_SPEED)

    @property
    def model_path(self) -> Path:
        """Path to the local model checkpoint."""
        return self._model_path

    @property
    def ffmpeg_bin(self) -> str:
        """Configured ffmpeg binary."""
        return self._ffmpeg_bin

    @property
    def default_sample_rate(self) -> int:
        """Default sample rate applied when requests omit one."""
        return self._default_sample_rate

    @property
    def default_speed(self) -> float:
        """Default speed applied when requests omit one."""
        return self._default_speed

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Return synthesized audio for the provided request."""
        normalized = self._normalize_request(request)
        if normalized.speed is None or normalized.sample_rate is None:
            raise AssertionError("Normalized request missing speed/sample_rate")
        normalized_speed = float(normalized.speed)
        normalized_sample_rate = int(normalized.sample_rate)
        cache_key = make_cache_key(
            model_path=str(self.model_path),
            text=normalized.text,
            speed=normalized_speed,
            sample_rate=normalized_sample_rate,
            format="txt",
        )
        utils.LOGGER.debug("Synth request", extra={"key": cache_key})
        if not normalized.dry_run:
            cached_path = self._cache.get_cached_path(cache_key)
            if cached_path:
                target_path = self._handle_target_path(
                    normalized, Path(cached_path)
                )
                return SynthesisResult(
                    request=normalized,
                    output_path=target_path,
                    from_cache=True,
                )

        if normalized.dry_run:
            placeholder_path = normalized.output_path or (
                self._cache.base_dir / "dry_run" / f"{cache_key}.txt"
            )
            return SynthesisResult(
                request=normalized,
                output_path=placeholder_path,
                from_cache=False,
            )

        safe_text = scrub(normalized.text)
        rendered = self._render_placeholder(safe_text, normalized)
        metadata = {
            "model_path": str(self.model_path),
            "sample_rate": normalized_sample_rate,
            "speed": normalized_speed,
            "format": "txt",
        }
        cache_path = Path(
            self._cache.store(cache_key, rendered.encode("utf-8"), metadata)
        )
        target_path = self._handle_target_path(
            normalized, cache_path, contents=rendered
        )
        return SynthesisResult(
            request=normalized,
            output_path=target_path,
            from_cache=False,
        )

    def _normalize_request(self, request: SynthesisRequest) -> SynthesisRequest:
        if not request.text.strip():
            raise ValueError("Input text must not be empty.")
        sample_rate = request.sample_rate or self._default_sample_rate
        speed = request.speed if request.speed is not None else self._default_speed
        if speed <= 0:
            raise ValueError("Speed must be greater than zero.")
        normalized = replace(
            request,
            sample_rate=sample_rate,
            speed=speed,
            voice=request.voice or DEFAULT_VOICE,
        )
        return normalized

    def _handle_target_path(
        self,
        request: SynthesisRequest,
        cached_path: Path,
        *,
        contents: str | None = None,
    ) -> Path:
        if request.output_path:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            if contents is None:
                contents = cached_path.read_text(encoding="utf-8")
            utils.atomic_write_text(request.output_path, contents)
            return request.output_path
        return cached_path

    def _render_placeholder(self, text: str, request: SynthesisRequest) -> str:
        return (
            "# Local Korean TTS placeholder\n"
            f"model={self.model_path}\n"
            f"ffmpeg={self.ffmpeg_bin}\n"
            f"voice={request.voice}\n"
            f"sample_rate={request.sample_rate}\n"
            f"speed={request.speed}\n\n"
            f"{text}\n"
        )
