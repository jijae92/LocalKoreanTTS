"""Shim package to expose src/localkoreantts without installation."""
from __future__ import annotations

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

__path__ = [str(_SRC_ROOT / "localkoreantts")]

from .tts import (  # noqa: E402,F401
    LocalVITS,
    SynthesisRequest,
    SynthesisResult,
    TextToSpeechEngine,
    load_model,
)

__all__ = [
    "LocalVITS",
    "SynthesisRequest",
    "SynthesisResult",
    "TextToSpeechEngine",
    "load_model",
]

__version__ = "0.1.0"
