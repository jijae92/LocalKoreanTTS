"""Controls panel for synthesis parameters and actions."""
from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ControlsView(QWidget):
    """Widget exposing synthesis parameters and action buttons."""

    chunk_preview_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    preview_requested = Signal()
    save_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._speed_slider.setRange(60, 160)
        self._speed_slider.setValue(100)
        self._speed_label = QLabel("재생 속도: 1.00x", self)
        self._speed_slider.valueChanged.connect(self._update_speed_label)

        self._format_combo = QComboBox(self)
        self._format_combo.addItems(["wav", "ogg", "mp3"])

        self._silence_spin = QSpinBox(self)
        self._silence_spin.setRange(0, 300)
        self._silence_spin.setSuffix(" ms")
        self._silence_spin.setValue(120)

        self._sample_rate_spin = QSpinBox(self)
        self._sample_rate_spin.setRange(8_000, 96_000)
        self._sample_rate_spin.setValue(22_050)
        self._sample_rate_spin.setSuffix(" Hz")

        self._default_speed_spin = QDoubleSpinBox(self)
        self._default_speed_spin.setRange(0.1, 3.0)
        self._default_speed_spin.setSingleStep(0.05)
        self._default_speed_spin.setValue(1.0)

        self._chunk_button = QPushButton("청크 미리보기", self)
        self._chunk_button.clicked.connect(self.chunk_preview_requested.emit)

        self._start_button = QPushButton("합성 시작", self)
        self._start_button.clicked.connect(self.start_requested.emit)

        self._stop_button = QPushButton("정지", self)
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self.stop_requested.emit)

        self._preview_button = QPushButton("미리듣기", self)
        self._preview_button.clicked.connect(self.preview_requested.emit)

        self._save_button = QPushButton("결과 저장 위치…", self)
        self._save_button.clicked.connect(self.save_requested.emit)

        layout = QVBoxLayout(self)
        layout.addWidget(self._speed_label)
        layout.addWidget(self._speed_slider)

        grid = QHBoxLayout()
        grid.addWidget(QLabel("포맷:", self))
        grid.addWidget(self._format_combo)
        grid.addSpacing(12)
        grid.addWidget(QLabel("무음:", self))
        grid.addWidget(self._silence_spin)
        grid.addSpacing(12)
        grid.addWidget(QLabel("샘플레이트:", self))
        grid.addWidget(self._sample_rate_spin)
        grid.addSpacing(12)
        grid.addWidget(QLabel("기본 속도:", self))
        grid.addWidget(self._default_speed_spin)
        grid.addStretch(1)
        layout.addLayout(grid)

        button_row = QHBoxLayout()
        button_row.addWidget(self._chunk_button)
        button_row.addWidget(self._preview_button)
        button_row.addWidget(self._save_button)
        button_row.addStretch(1)
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._stop_button)
        layout.addLayout(button_row)

        self._update_speed_label(self._speed_slider.value())
        self._start_allowed: bool = False
        self._running: bool = False

    def current_speed(self) -> float:
        """Return the selected playback speed."""
        value = int(self._speed_slider.value())
        return round(value / 100.0, 2)

    def current_format(self) -> str:
        """Return the requested output format."""
        return self._format_combo.currentText()

    def silence_milliseconds(self) -> int:
        """Return the silence padding between chunks."""
        return int(self._silence_spin.value())

    def sample_rate(self) -> int:
        """Return the preferred sample rate."""
        return int(self._sample_rate_spin.value())

    def default_speed(self) -> float:
        """Return the preferred default speed setting."""
        return float(self._default_speed_spin.value())

    def set_start_enabled(self, enabled: bool) -> None:
        """Enable or disable the start button."""
        self._start_allowed = enabled
        self._refresh_start_state()

    def set_running_state(self, running: bool) -> None:
        """Toggle button states based on worker activity."""
        self._running = running
        self._refresh_start_state()
        self._stop_button.setEnabled(running)
        self._preview_button.setEnabled(not running)
        self._chunk_button.setEnabled(not running)

    def apply_settings(self, sample_rate: int, default_speed: float) -> None:
        """Synchronise controls with persisted settings."""
        self._sample_rate_spin.setValue(sample_rate)
        self._default_speed_spin.setValue(default_speed)

    def _update_speed_label(self, value: int) -> None:
        factor = value / 100.0
        self._speed_label.setText(f"재생 속도: {factor:.2f}x")

    def _refresh_start_state(self) -> None:
        self._start_button.setEnabled(self._start_allowed and not self._running)
