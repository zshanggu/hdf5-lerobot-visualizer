from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class Player(QObject):
    """Drives frame-index playback for a demo at its recorded control frequency."""

    frame_changed = Signal(int)
    playing_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._num_frames = 0
        self._frame = 0
        self._base_fps = 20.0
        self._speed = 1.0

    def configure(self, num_frames: int, fps: float) -> None:
        self.stop()
        self._num_frames = max(num_frames, 0)
        self._base_fps = max(fps, 1e-3)
        self._frame = 0
        self._apply_interval()
        self.frame_changed.emit(self._frame)

    def set_speed(self, speed: float) -> None:
        self._speed = max(speed, 0.05)
        self._apply_interval()

    def _apply_interval(self) -> None:
        interval_ms = int(1000 / (self._base_fps * self._speed))
        self._timer.setInterval(max(interval_ms, 1))

    def is_playing(self) -> bool:
        return self._timer.isActive()

    def play(self) -> None:
        if self._num_frames <= 1:
            return
        if self._frame >= self._num_frames - 1:
            self._frame = 0
        self._timer.start()
        self.playing_changed.emit(True)

    def pause(self) -> None:
        self._timer.stop()
        self.playing_changed.emit(False)

    def stop(self) -> None:
        self._timer.stop()
        self.playing_changed.emit(False)

    def toggle(self) -> None:
        self.pause() if self.is_playing() else self.play()

    def seek(self, frame: int) -> None:
        self._frame = max(0, min(frame, max(self._num_frames - 1, 0)))
        self.frame_changed.emit(self._frame)

    def step(self, delta: int) -> None:
        self.pause()
        self.seek(self._frame + delta)

    def _advance(self) -> None:
        if self._frame >= self._num_frames - 1:
            self.pause()
            return
        self._frame += 1
        self.frame_changed.emit(self._frame)
