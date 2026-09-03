from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget


class TrajectoryPlot(QWidget):
    """Matplotlib line plot of a chosen signal over time, with a frame cursor.

    Available signal names come from whatever `Episode.signals` the current
    demo/episode provides -- this makes the plot agnostic to the data source
    (raw LIBERO HDF5 vs. a LeRobot dataset expose different signal sets).
    """

    signals_changed = Signal(list)  # emits the new list of available signal names

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._figure = Figure(figsize=(5, 3), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._cursor_line = None
        self._episode = None
        self._signal_name: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def set_signal(self, signal_name: str) -> None:
        self._signal_name = signal_name
        self._redraw()

    def set_episode(self, episode) -> None:
        self._episode = episode
        names = list(episode.signals.keys()) if episode is not None else []
        if self._signal_name not in names:
            self._signal_name = names[0] if names else None
        self.signals_changed.emit(names)
        self._redraw()

    def _redraw(self) -> None:
        self._ax.clear()
        self._cursor_line = None
        if (
            self._episode is None
            or self._signal_name is None
            or self._signal_name not in self._episode.signals
        ):
            self._canvas.draw_idle()
            return

        data, labels = self._episode.signals[self._signal_name]
        t = np.arange(data.shape[0]) / max(self._episode.fps, 1e-6)
        for dim in range(data.shape[1]):
            label = labels[dim] if dim < len(labels) else f"dim{dim}"
            self._ax.plot(t, data[:, dim], label=label, linewidth=1.2)

        self._ax.set_xlabel("time (s)")
        self._ax.set_ylabel(self._signal_name)
        self._ax.legend(loc="upper right", fontsize=8, ncol=min(data.shape[1], 4))
        self._ax.grid(True, alpha=0.3)
        self._cursor_line = self._ax.axvline(0.0, color="red", linewidth=1.0)
        self._canvas.draw_idle()

    def set_frame_index(self, index: int) -> None:
        if self._episode is None or self._cursor_line is None:
            return
        t = index / max(self._episode.fps, 1e-6)
        self._cursor_line.set_xdata([t, t])
        self._canvas.draw_idle()
