from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .subskill_boundaries import color_for_skill

_MIN_LABEL_WIDTH_PX = 28  # below this segment width, skip drawing the prompt text (would just be clipped noise)


class SubskillTimeline(QWidget):
    """A colored segment bar showing each sub-skill's [start_frame, end_frame]
    span, drawn to line up horizontally with the frame slider above/below it.

    Purely a display widget -- click/drag isn't wired to seeking (the slider
    already does that); this only shows the boundaries and the current frame
    position, plus a tooltip with the full prompt text on hover (segments are
    often too narrow to fit their label).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._num_frames = 1
        self._boundaries: list[dict] | None = None
        self._current_frame = 0
        self.setMinimumHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setVisible(False)

    def set_episode(self, num_frames: int, boundaries: list[dict] | None) -> None:
        self._num_frames = max(num_frames, 1)
        self._boundaries = boundaries
        self._current_frame = 0
        self.setVisible(bool(boundaries))
        self.update()

    def set_frame_index(self, index: int) -> None:
        self._current_frame = index
        if self._boundaries:
            self.update()

    def _frame_to_x(self, frame: float) -> float:
        span = max(self._num_frames - 1, 1)
        return frame / span * self.width()

    def _segment_at(self, x: float) -> dict | None:
        if not self._boundaries:
            return None
        frame = x / max(self.width(), 1) * max(self._num_frames - 1, 1)
        for b in self._boundaries:
            if b["start_frame"] <= frame <= b["end_frame"] + 1:
                return b
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        seg = self._segment_at(event.position().x())
        if seg is None:
            self.setToolTip("")
        else:
            note = "  (boundary uncertain)" if seg.get("detection_failed") else ""
            self.setToolTip(f"{seg['prompt']}{note}\nframes {seg['start_frame']}-{seg['end_frame']}")
        super().mouseMoveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if not self._boundaries:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()

        for b in self._boundaries:
            x0 = self._frame_to_x(b["start_frame"])
            x1 = self._frame_to_x(b["end_frame"] + 1)
            rect = QRectF(x0, 2, max(x1 - x0, 1.0), h - 4)
            color = color_for_skill(b["skill_idx"])
            painter.fillRect(rect, color)
            if b.get("detection_failed"):
                pen = QPen(QColor("white"))
                pen.setStyle(Qt.PenStyle.DashLine)
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawRect(rect.adjusted(0.5, 0.5, -0.5, -0.5))

            if rect.width() >= _MIN_LABEL_WIDTH_PX:
                painter.setPen(QColor("white"))
                text_rect = rect.adjusted(3, 0, -3, 0)
                elided = painter.fontMetrics().elidedText(
                    b["prompt"], Qt.TextElideMode.ElideRight, int(text_rect.width())
                )
                painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided)

        cx = self._frame_to_x(self._current_frame)
        painter.setPen(QPen(QColor("black"), 2))
        painter.drawLine(int(cx), 0, int(cx), h)
