from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import sources


class ScanWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        try:
            tasks = sources.scan_path(self._path)
        except Exception as exc:  # noqa: BLE001 - surface any error to the UI
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(tasks)


class LoadEpisodeWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, task: sources.Task, demo_key: str, parent=None):
        super().__init__(parent)
        self._task = task
        self._demo_key = demo_key

    def run(self) -> None:
        try:
            episode = sources.load_episode(self._task, self._demo_key)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(episode)
