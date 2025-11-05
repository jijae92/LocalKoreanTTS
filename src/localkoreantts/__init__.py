"""Local Korean TTS core package."""

from .tts import (
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
