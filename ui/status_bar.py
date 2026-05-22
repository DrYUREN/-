"""自定义状态栏。显示采集FPS、推理FPS、检测数量、设备状态。"""

from PyQt5.QtWidgets import QStatusBar, QLabel


class CustomStatusBar(QStatusBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._capture_fps_label = QLabel("采集: -- FPS")
        self._capture_fps_label.setMinimumWidth(120)
        self._inference_fps_label = QLabel("推理: -- FPS")
        self._inference_fps_label.setMinimumWidth(120)
        self._detection_label = QLabel("检测: 0")
        self._detection_label.setMinimumWidth(100)
        self._device_label = QLabel("设备: --")

        self.addPermanentWidget(self._device_label)
        self.addPermanentWidget(self._capture_fps_label)
        self.addPermanentWidget(self._inference_fps_label)
        self.addPermanentWidget(self._detection_label)

        self.setStyleSheet("QStatusBar { background: #16213e; color: #ccc; }")

    def set_capture_fps(self, fps: float) -> None:
        self._capture_fps_label.setText(f"采集: {fps:.1f} FPS")

    def set_inference_fps(self, fps: float) -> None:
        self._inference_fps_label.setText(f"推理: {fps:.1f} FPS")

    def set_detection_count(self, count: int) -> None:
        self._detection_label.setText(f"检测: {count}")

    def set_device_status(self, status: str) -> None:
        self._device_label.setText(f"设备: {status}")
