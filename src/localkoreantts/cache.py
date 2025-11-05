"""Integrity-hashed cache management for synthesized outputs."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from . import utils

_METADATA_EXT = ".json"


def make_cache_key(
    model_path: str,
    text: str,
    speed: float,
    sample_rate: int,
    format: str,
) -> str:
    """Return a deterministic cache key for a synthesis request."""
    text_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload = {
        "format": format,
        "model_path": str(Path(model_path).expanduser().resolve()),
        "sample_rate": int(sample_rate),
        "speed": float(speed),
        "text_hash": text_digest,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CacheManager:
    """Manage cached synthesis artefacts on disk with integrity checks."""

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        base = utils.resolve_cache_dir(cache_dir)
        self._base_dir = utils.ensure_directory(base)

    @property
    def base_dir(self) -> Path:
        """Return the root cache directory."""
        return self._base_dir

    def get_cached_path(self, key: str) -> str | None:
        """Return the cached payload path when both file and metadata are valid."""
        metadata = self._load_metadata(key)
        if not metadata:
            return None
        payload_path = self._payload_path(key, metadata.get("format", "wav"))
        if not payload_path.exists():
            return None
        payload_hash = metadata.get("payload_hash")
        if payload_hash and not self.verify_cached_file(
            str(payload_path), payload_hash
        ):
            utils.LOGGER.warning(
                "Cache verification failed; deleting corrupt entry",
                extra={"key": key, "path": str(payload_path)},
            )
            self._safe_unlink(payload_path)
            self._safe_unlink(self._metadata_path(key))
            return None
        utils.LOGGER.debug(
            "Cache hit", extra={"key": key, "payload": str(payload_path)}
        )
        return str(payload_path)

    def store(self, key: str, wav_bytes: bytes, metadata: dict[str, Any]) -> str:
        """Persist a WAV payload and accompanying metadata atomically."""
        if not isinstance(wav_bytes, bytes | bytearray):
            raise TypeError("wav_bytes must be raw bytes.")
        record_dir = self._key_directory(key)
        utils.ensure_directory(record_dir)

        record_metadata = dict(metadata)
        record_metadata.setdefault("format", "wav")
        record_metadata["key"] = key
        record_metadata["created_at"] = time.time()
        record_metadata["payload_hash"] = hashlib.sha256(wav_bytes).hexdigest()

        payload_path = self._payload_path(key, record_metadata["format"])
        metadata_path = self._metadata_path(key)

        utils.atomic_write_bytes(payload_path, bytes(wav_bytes))
        metadata_json = json.dumps(
            record_metadata, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        utils.atomic_write_bytes(metadata_path, metadata_json)

        utils.LOGGER.debug(
            "Stored cache entry",
            extra={
                "key": key,
                "payload": str(payload_path),
                "metadata": str(metadata_path),
            },
        )
        return str(payload_path)

    def verify_cached_file(self, path: str, metadata_hash: str) -> bool:
        """Verify the cached file by comparing its hash against stored metadata."""
        file_path = Path(path)
        if not file_path.exists():
            return False
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        is_valid = digest.hexdigest() == metadata_hash
        if not is_valid:
            utils.LOGGER.warning(
                "Cache payload hash mismatch",
                extra={"path": str(file_path)},
            )
        return is_valid

    # Compatibility helpers for legacy usage ---------------------------------
    def build_key(
        self, *, text: str, voice: str, speed: float, sample_rate: int
    ) -> str:
        """Backwards-compatible wrapper building a cache key for textual artefacts."""
        return make_cache_key(
            model_path=voice or "default",
            text=text,
            speed=speed,
            sample_rate=sample_rate,
            format="txt",
        )

    def get(self, key: str) -> _CacheRecordCompat | None:
        """Backwards-compatible retrieval returning a simple namespace-style object."""
        cached_path = self.get_cached_path(key)
        if not cached_path:
            return None
        metadata = self._load_metadata(key)
        created_at = (
            float(metadata.get("created_at", time.time()))
            if metadata
            else time.time()
        )
        return _CacheRecordCompat(
            key=key, payload_path=Path(cached_path), created_at=created_at
        )

    def set(
        self, key: str, contents: str, extension: str = ".txt"
    ) -> _CacheRecordCompat:
        """Backwards-compatible setter storing textual payloads."""
        data = contents.encode("utf-8")
        metadata = {
            "format": extension.lstrip(".") or "txt",
        }
        payload_path = self.store(key, data, metadata)
        return _CacheRecordCompat(
            key=key, payload_path=Path(payload_path), created_at=time.time()
        )

    # Internal helpers -------------------------------------------------------
    def _key_directory(self, key: str) -> Path:
        prefix = key[:2] if len(key) >= 2 else key
        return self._base_dir / prefix

    def _payload_path(self, key: str, format_name: str) -> Path:
        suffix = f".{format_name}" if not format_name.startswith(".") else format_name
        return self._key_directory(key) / f"{key}{suffix}"

    def _metadata_path(self, key: str) -> Path:
        return self._key_directory(key) / f"{key}{_METADATA_EXT}"

    def _load_metadata(self, key: str) -> dict[str, Any] | None:
        metadata_path = self._metadata_path(key)
        if not metadata_path.exists():
            return None
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return None
        except json.JSONDecodeError:  # pragma: no cover - defensive
            utils.LOGGER.warning("Failed to decode cache metadata", extra={"key": key})
            return None

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:  # pragma: no cover - defensive
            return
        except OSError:  # pragma: no cover - best effort cleanup
            utils.LOGGER.warning(
                "Failed to remove cache artefact", extra={"path": str(path)}
            )


class _CacheRecordCompat:
    """Minimal shim providing the legacy CacheRecord attributes."""

    def __init__(self, key: str, payload_path: Path, created_at: float) -> None:
        self.key = key
        self.payload_path = payload_path
        self.created_at = created_at

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"_CacheRecordCompat(key={self.key!r}, "
            f"payload_path={str(self.payload_path)!r})"
        )
