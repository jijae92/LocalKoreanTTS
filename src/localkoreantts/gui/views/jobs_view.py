"""Widget representing the synthesis job queue."""
from __future__ import annotations

# ruff: noqa: I001

from enum import Enum

from PySide6.QtCore import Qt  # type: ignore[import-not-found]
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem  # type: ignore[import-not-found]


class JobStatus(Enum):
    """Possible job lifecycle states."""

    QUEUED = "대기"
    RUNNING = "진행 중"
    COMPLETED = "완료"
    FAILED = "실패"
    CANCELLED = "취소됨"


class JobState:
    """In-memory representation of a job displayed in the queue."""

    def __init__(self, job_id: int, description: str, status: JobStatus) -> None:
        self.job_id = job_id
        self.description = description
        self.status = status
        self.detail: str = ""
        self.result_path: str | None = None


class JobsView(QTreeWidget):  # type: ignore[misc]
    """Tree widget listing queued synthesis jobs."""

    def __init__(self, parent: QTreeWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels(["작업", "상태", "세부 정보"])
        self.setRootIsDecorated(False)
        self._items: dict[int, QTreeWidgetItem] = {}

    def update_job(self, state: JobState) -> None:
        """Insert or update a job row."""
        if state.job_id in self._items:
            item = self._items[state.job_id]
        else:
            item = QTreeWidgetItem(self)
            item.setTextAlignment(0, Qt.AlignLeft | Qt.AlignVCenter)
            item.setTextAlignment(1, Qt.AlignCenter)
            self._items[state.job_id] = item

        item.setText(0, f"#{state.job_id} {state.description}")
        item.setText(1, state.status.value)
        item.setText(2, state.detail or "")

    def reset(self) -> None:
        """Clear the queue."""
        self.clear()
        self._items.clear()

    def remove_job(self, job_id: int) -> None:
        """Remove a job from the view."""
        item = self._items.pop(job_id, None)
        if item is None:
            return
        index = self.indexOfTopLevelItem(item)
        if index >= 0:
            self.takeTopLevelItem(index)
