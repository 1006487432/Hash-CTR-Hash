from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, str)
    partial = Signal(object)


class TaskRunner(QRunnable):
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # pragma: no cover - GUI boundary
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(result)


class StreamingTaskRunner(QRunnable):
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self.fn(
                *self.args,
                progress_callback=self.signals.progress.emit,
                partial_callback=self.signals.partial.emit,
                **self.kwargs,
            )
        except Exception as exc:  # pragma: no cover - GUI boundary
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(result)


def start_task(fn: Callable, on_success: Callable, on_error: Callable, *args, **kwargs) -> None:
    runner = TaskRunner(fn, *args, **kwargs)
    runner.signals.finished.connect(on_success, Qt.ConnectionType.QueuedConnection)
    runner.signals.failed.connect(on_error, Qt.ConnectionType.QueuedConnection)
    QThreadPool.globalInstance().start(runner)


def start_streaming_task(
    fn: Callable,
    on_success: Callable,
    on_error: Callable,
    on_progress: Callable,
    on_partial: Callable,
    *args,
    **kwargs,
) -> None:
    runner = StreamingTaskRunner(fn, *args, **kwargs)
    runner.signals.finished.connect(on_success, Qt.ConnectionType.QueuedConnection)
    runner.signals.failed.connect(on_error, Qt.ConnectionType.QueuedConnection)
    runner.signals.progress.connect(on_progress, Qt.ConnectionType.QueuedConnection)
    runner.signals.partial.connect(on_partial, Qt.ConnectionType.QueuedConnection)
    QThreadPool.globalInstance().start(runner)
