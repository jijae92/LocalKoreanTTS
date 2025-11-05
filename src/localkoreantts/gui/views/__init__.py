"""Composite widgets used by the Local Korean TTS GUI."""
from __future__ import annotations

from .controls_view import ControlsView
from .editor_view import EditorView, FileInputView
from .jobs_view import JobState, JobStatus, JobsView
from .log_view import LogView
from .settings_dialog import SettingsData, SettingsDialog, validate_settings_data

__all__ = [
    "ControlsView",
    "EditorView",
    "FileInputView",
    "JobState",
    "JobStatus",
    "JobsView",
    "LogView",
    "SettingsData",
    "SettingsDialog",
    "validate_settings_data",
]
