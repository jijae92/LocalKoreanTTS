"""Qt worker that bridges the synthesis pipeline to the GUI."""
from __future__ import annotations

# ruff: noqa: I001

from typing import Any, TYPE_CHECKING

from ... import utils
from ..pipeline import (
    JobCancelled,
    PipelineHooks,
    SynthJobConfig,
    run_synthesis_pipeline,
)

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from PySide6.QtCore import QObject, Signal  # type: ignore[import-not-found]

    class SynthWorker(QObject):  # type: ignore[misc]
        progress: Signal
        stage: Signal
        chunk_done: Signal
        finished: Signal
        error: Signal
        cancelled: Signal
        log: Signal

        def __init__(
            self, config: SynthJobConfig, parent: QObject | None = None
        ) -> None: ...
        def request_cancel(self) -> None: ...
        def run(self) -> None: ...

else:
    _IMPORT_ERROR: BaseException | None = None
    try:  # pragma: no cover - optional dependency
        from PySide6.QtCore import QObject, Signal  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - optional dependency
        _IMPORT_ERROR = exc

        class SynthWorker:  # type: ignore[misc]
            """Fallback worker raising a helpful error when PySide6 is unavailable."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
                raise RuntimeError(
                    "PySide6 is required to use SynthWorker."
                ) from _IMPORT_ERROR

            def request_cancel(self) -> None:  # pragma: no cover - defensive
                raise RuntimeError(
                    "PySide6 is required to use SynthWorker."
                ) from _IMPORT_ERROR

            def run(self) -> None:  # pragma: no cover - defensive
                raise RuntimeError(
                    "PySide6 is required to use SynthWorker."
                ) from _IMPORT_ERROR

    else:

        import time

        class SynthWorker(QObject):  # type: ignore[misc]
            """Background worker executing synthesis jobs."""

            progress = Signal(int)
            stage = Signal(str)
            chunk_done = Signal(int, int)
            finished = Signal(str)
            error = Signal(str)
            cancelled = Signal()
            log = Signal(str)

            def __init__(
                self, config: SynthJobConfig, parent: QObject | None = None
            ) -> None:
                super().__init__(parent)
                self._config = config
                self._cancelled = False

            def request_cancel(self) -> None:
                """Signal the worker to cancel."""
                self._cancelled = True

            def run(self) -> None:
                """Execute the pipeline and emit Qt signals."""
                start_time = time.time()
                utils.LOGGER.info(
                    "GUI job started", extra={"job_id": self._config.job_id}
                )

                def _on_progress(done: int, total: int) -> None:
                    elapsed = max(time.time() - start_time, 0.0)
                    percent = int((done / total) * 100) if total else 100
                    self.progress.emit(percent)
                    if total:
                        remaining = max(total - done, 0)
                        eta = 0.0
                        if done:
                            estimated_total = (elapsed / done) * total
                            eta = max(estimated_total - elapsed, 0.0)
                        self.stage.emit(
                            f"progress:{done}/{total}:remaining={remaining}:eta={eta:.1f}s"
                        )

                hooks = PipelineHooks(
                    should_cancel=lambda: self._cancelled,
                    on_progress=_on_progress,
                    on_log=self.log.emit,
                    on_stage=self.stage.emit,
                    on_chunk_done=lambda done, total: self.chunk_done.emit(done, total),
                )

                try:
                    result = run_synthesis_pipeline(self._config, hooks)
                except JobCancelled:
                    utils.LOGGER.info(
                        "GUI job cancelled", extra={"job_id": self._config.job_id}
                    )
                    self.cancelled.emit()
                except Exception as exc:  # pragma: no cover - defensive
                    utils.LOGGER.exception(
                        "GUI job failed", extra={"job_id": self._config.job_id}
                    )
                    self.error.emit(str(exc))
                else:
                    utils.LOGGER.info(
                        "GUI job completed", extra={"job_id": self._config.job_id}
                    )
                    self.finished.emit(str(result.output_path))
                finally:
                    self._cancelled = False
