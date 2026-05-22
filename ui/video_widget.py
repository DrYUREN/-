"""视频显示组件。将 OpenCV BGR 图像转为 QPixmap 显示。"""

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


class VideoDisplayWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._label = QLabel("等待视频信号...")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("""
            QLabel {
                background-color: #1a1a2e;
                color: #888;
                font-size: 16px;
                border: 2px solid #2a2a4e;
                border-radius: 8px;
            }
        """)
        self._label.setMinimumSize(640, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self._current_frame: np.ndarray | None = None

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        self._current_frame = frame_bgr
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        scaled = qimg.scaled(
            self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._label.setPixmap(QPixmap.fromImage(scaled))

    def clear(self) -> None:
        self._label.clear()
        self._label.setText("等待视频信号...")
        self._current_frame = None

    @property
    def current_frame(self) -> np.ndarray | None:
        return self._current_frame
