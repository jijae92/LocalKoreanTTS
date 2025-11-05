"""Settings dialog for configuring synthesis defaults."""
from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (  # type: ignore[import-not-found]
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ... import utils


@dataclass
class SettingsData:
    """Persisted user preferences."""

    model_path: Path
    cache_dir: Path
    ffmpeg_bin: str
    sample_rate: int
    default_speed: float


class SettingsDialog(QDialog):  # type: ignore[misc]
    """Modal dialog used to edit persistent settings."""

    def __init__(
        self,
        current: SettingsData,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setModal(True)
        self._data = current

        self._model_edit = QLineEdit(str(current.model_path), self)
        self._cache_edit = QLineEdit(str(current.cache_dir), self)
        self._ffmpeg_edit = QLineEdit(current.ffmpeg_bin, self)

        self._sample_rate_spin = QSpinBox(self)
        self._sample_rate_spin.setRange(8_000, 96_000)
        self._sample_rate_spin.setValue(current.sample_rate)
        self._sample_rate_spin.setSuffix(" Hz")

        self._default_speed_spin = QDoubleSpinBox(self)
        self._default_speed_spin.setRange(0.1, 3.0)
        self._default_speed_spin.setSingleStep(0.05)
        self._default_speed_spin.setValue(current.default_speed)

        form = QFormLayout()
        form.addRow(
            "모델 경로",
            self._with_browse(self._model_edit, self._browse_model),
        )
        form.addRow(
            "캐시 디렉터리",
            self._with_browse(self._cache_edit, self._browse_cache),
        )
        form.addRow(
            "FFmpeg 실행 파일",
            self._with_browse(self._ffmpeg_edit, self._browse_ffmpeg),
        )
        form.addRow("샘플레이트", self._sample_rate_spin)
        form.addRow("기본 속도", self._default_speed_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def settings(self) -> SettingsData:
        """Return the updated settings."""
        return self._data

    def accept(self) -> None:
        model_path = Path(self._model_edit.text().strip() or utils.default_model_path())
        cache_dir = Path(self._cache_edit.text().strip() or utils.default_cache_dir())
        ffmpeg_bin = self._ffmpeg_edit.text().strip() or utils.resolve_ffmpeg_bin()
        data = SettingsData(
            model_path=model_path,
            cache_dir=cache_dir,
            ffmpeg_bin=ffmpeg_bin,
            sample_rate=int(self._sample_rate_spin.value()),
            default_speed=float(self._default_speed_spin.value()),
        )
        valid, details, error = validate_settings_data(data)
        if not valid:
            QMessageBox.warning(self, "설정 오류", error)
            return
        self._data = data
        super().accept()

    def _with_browse(
        self,
        line_edit: QLineEdit,
        callback: Callable[[], None],
    ) -> QHBoxLayout:
        container = QHBoxLayout()
        container.addWidget(line_edit, stretch=1)
        button = QPushButton("찾아보기…", self)
        button.clicked.connect(callback)
        container.addWidget(button)
        return container

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "모델 파일 선택",
            str(self._model_edit.text().strip()),
        )
        if path:
            self._model_edit.setText(path)

    def _browse_cache(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "캐시 디렉터리 선택",
            str(self._cache_edit.text().strip()),
        )
        if path:
            self._cache_edit.setText(path)

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "FFmpeg 실행 파일 선택",
            str(self._ffmpeg_edit.text().strip()),
        )
        if path:
            self._ffmpeg_edit.setText(path)


def validate_settings_data(
    data: SettingsData,
) -> tuple[bool, dict[str, bool], str]:
    """Validate settings and return status flags per category."""

    errors: list[str] = []

    model_ok = data.model_path.exists()
    if not model_ok:
        errors.append("모델 경로가 존재하지 않습니다.")

    cache_ok = data.cache_dir.exists()
    if not cache_ok:
        try:
            data.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_ok = True
        except OSError:
            errors.append("캐시 디렉터리를 생성하거나 찾을 수 없습니다.")

    ffmpeg_ok = _validate_ffmpeg_binary(data.ffmpeg_bin)
    if not ffmpeg_ok:
        errors.append("FFmpeg 실행 파일을 확인하세요.")

    status = {"model": model_ok, "cache": cache_ok, "ffmpeg": ffmpeg_ok}
    message = "\n".join(errors)
    return not errors, status, message


def _validate_ffmpeg_binary(candidate: str) -> bool:
    path = Path(candidate)
    resolved: str | None
    if path.exists():
        resolved = str(path)
    else:
        resolved = shutil.which(candidate)
    if not resolved:
        return False
    if not os.access(resolved, os.X_OK):
        return False
    try:
        subprocess.run(
            [resolved, "--version"],
            check=True,
            timeout=5,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True
