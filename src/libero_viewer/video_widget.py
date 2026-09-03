from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class CameraView(QWidget):
    """Displays one camera's RGB frame stream, scaled to fill its space.

    Frames are displayed exactly as given -- any orientation fix-up (e.g. for
    MuJoCo's bottom-to-top row order) is the data backend's responsibility,
    since it's a source-format detail, not a display concern.
    """

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._label_title = QLabel(title, self)
        self._label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_title.setStyleSheet("font-weight: 600; color: #ccc;")

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(128, 128)
        self._image_label.setStyleSheet("background-color: #111;")
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addWidget(self._label_title)
        layout.addWidget(self._image_label, 1)

        self._frame: np.ndarray | None = None

    def set_title(self, title: str) -> None:
        self._label_title.setText(title)

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = np.ascontiguousarray(frame)
        self._refresh()

    def clear(self) -> None:
        self._frame = None
        self._image_label.clear()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._frame is None:
            return
        h, w, ch = self._frame.shape
        qimage = QImage(self._frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(pixmap)
