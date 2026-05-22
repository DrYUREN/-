"""主窗口。管理数据源、模型选择、播放控制、病灶截图面板。"""

import logging
import os

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QMessageBox, QGroupBox,
)

from core.frame_buffer import FrameBuffer
from core.capture import CaptureWorker
from core.detector import InferenceWorker
from ui.video_widget import VideoDisplayWidget
from ui.control_panel import ControlPanel
from ui.detection_table import DetectionResultTable
from ui.status_bar import CustomStatusBar
from ui.lesion_panel import LesionPanel
from utils.device_enumerator import enumerate_capture_devices
from utils.video_writer import VideoRecorder, save_screenshot


class MainWindow(QMainWindow):
    def __init__(self, config: dict, classes_config: dict) -> None:
        super().__init__()
        self._config = config
        self._classes_config = classes_config
        self._logger = logging.getLogger("胃镜精灵")

        self._frame_buffer = FrameBuffer()
        self._capture_worker = CaptureWorker(self._frame_buffer)
        self._inference_worker = InferenceWorker(self._frame_buffer, config, classes_config)
        self._recorder = VideoRecorder(
            output_dir=config.get("recording", {}).get("output_dir", "recordings"),
            fps=config.get("recording", {}).get("fps", 30),
            codec=config.get("recording", {}).get("codec", "mp4v"),
        )

        self._init_ui()
        self._connect_signals()
        self._load_devices()

    def _init_ui(self) -> None:
        ui_cfg = self._config.get("ui", {})
        self.setWindowTitle(ui_cfg.get("window_title", "胃镜精灵"))
        w, h = ui_cfg.get("default_window_size", [1600, 900])
        self.resize(w, h)
        self.setMinimumSize(1200, 700)

        self.setStyleSheet("""
            QMainWindow { background-color: #0f0f23; }
            QGroupBox { color: #ccc; font-weight: bold; font-size: 12px;
                border: 1px solid #2a2a4e; border-radius: 6px;
                margin-top: 10px; padding-top: 14px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QLabel { color: #ccc; }
            QComboBox { background:#1a1a3e; color:#fff; border:1px solid #3a3a5e;
                border-radius:4px; padding:3px 6px; }
            QComboBox::drop-down { border:none; }
            QComboBox QAbstractItemView { background:#1a1a3e; color:#fff;
                selection-background-color:#2a5a7e; }
            QTableWidget { background:#1a1a3e; color:#ccc;
                alternate-background-color:#1f1f44; gridline-color:#2a2a4e;
                border:1px solid #2a2a4e; border-radius:4px; }
            QTableWidget::item { padding:3px; }
            QHeaderView::section { background:#16213e; color:#aab;
                border:1px solid #2a2a4e; padding:3px; }
            QPushButton { background:#2a2a5e; color:#ccc; border:1px solid #3a3a6e;
                border-radius:4px; padding:5px 10px; }
            QPushButton:hover { background:#3a3a7e; }
            QPushButton:disabled { background:#333; color:#666; }
            QSlider::groove:horizontal { background:#2a2a4e; height:5px; border-radius:3px; }
            QSlider::handle:horizontal { background:#4a9eff; width:14px; height:14px;
                margin:-4px 0; border-radius:7px; }
            QCheckBox, QRadioButton { color:#ccc; }
            QScrollArea { border:none; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)

        # 左侧：视频 + 检测表
        self._video_widget = VideoDisplayWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self._video_widget, 1)
        result_group = QGroupBox("实时检测结果")
        rl = QVBoxLayout(result_group)
        self._detection_table = DetectionResultTable()
        rl.addWidget(self._detection_table)
        left_layout.addWidget(result_group, 0)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # 中间：控制面板
        self._control_panel = ControlPanel()

        # 右侧：病灶截图面板
        self._lesion_panel = LesionPanel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(self._control_panel)
        splitter.addWidget(self._lesion_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter)

        self._status_bar = CustomStatusBar()
        self.setStatusBar(self._status_bar)

    def _connect_signals(self) -> None:
        cp = self._control_panel
        cp.start_clicked.connect(self._on_start)
        cp.stop_clicked.connect(self._on_stop)
        cp.confidence_changed.connect(self._on_confidence_changed)
        cp.clahe_toggled.connect(self._on_clahe_toggled)
        cp.screenshot_clicked.connect(self._on_screenshot)
        cp.record_toggled.connect(self._on_record_toggle)
        cp.source_type_changed.connect(self._on_source_type_changed)
        cp.video_file_selected.connect(self._on_video_file_selected)
        cp.model_file_selected.connect(self._on_model_file_selected)
        cp.pause_toggled.connect(self._on_pause_toggled)
        cp.speed_changed.connect(self._on_speed_changed)
        cp.seek_changed.connect(self._on_seek_changed)
        cp.set_refresh_callback(self._load_devices)

        cw = self._capture_worker
        cw.fps_update.connect(self._status_bar.set_capture_fps)
        cw.capture_error.connect(self._on_capture_error)
        cw.source_ended.connect(self._on_source_ended)
        cw.state_changed.connect(self._on_capture_state_changed)
        cw.progress_update.connect(self._on_progress_update)

        iw = self._inference_worker
        iw.result_ready.connect(self._on_result_ready)
        iw.inference_fps_update.connect(self._status_bar.set_inference_fps)
        iw.inference_error.connect(self._on_inference_error)
        iw.lesion_crops.connect(self._on_lesion_crops)

    def _load_devices(self) -> None:
        devices = enumerate_capture_devices()
        if devices:
            self._control_panel.populate_devices(devices)
            self._status_bar.set_device_status(f"已就绪 ({len(devices)}个设备)")
        else:
            self._status_bar.set_device_status("未找到设备")

    def _on_source_type_changed(self, source_type: str) -> None:
        if source_type == "file":
            self._status_bar.set_device_status("MP4 文件模式")
        elif source_type == "camera":
            self._status_bar.set_device_status("电脑摄像头模式")
        else:
            self._load_devices()
            self._status_bar.set_device_status("HDMI 采集模式")

    def _on_video_file_selected(self, path: str) -> None:
        vf_cfg = self._config.get("video_file", {})
        self._capture_worker.set_video_file(path, vf_cfg.get("loop_playback", True))
        self._status_bar.set_device_status(f"MP4: {os.path.basename(path)}")
        self._logger.info(f"视频文件已选择: {path}")

    def _on_model_file_selected(self, path: str) -> None:
        self._inference_worker.load_model(path)
        self._config["detection"]["model_path"] = path
        self._status_bar.showMessage(f"模型已切换: {os.path.basename(path)}", 3000)
        self._logger.info(f"模型切换: {path}")

    def _on_pause_toggled(self) -> None:
        self._capture_worker.toggle_pause()

    def _on_speed_changed(self, speed: float) -> None:
        self._capture_worker.set_speed(speed)

    def _on_seek_changed(self, position: float) -> None:
        self._capture_worker.seek(position)

    def _on_progress_update(self, pos: int, total: int, elapsed_ms: int, duration_ms: int) -> None:
        self._control_panel.update_progress(pos, total, elapsed_ms, duration_ms)

    def _on_capture_state_changed(self, state: str) -> None:
        if state == "paused":
            self._status_bar.showMessage("⏸ 已暂停", 0)
        else:
            self._status_bar.showMessage("▶ 播放中", 2000)

    def _on_start(self) -> None:
        source_type = self._control_panel.get_source_type()

        if source_type == "device":
            device_idx = self._control_panel.get_device_index()
            if device_idx is None:
                QMessageBox.warning(self, "无采集设备", "未检测到任何视频采集设备，请连接 HDMI 采集卡后刷新设备列表。")
                return
            cap_cfg = self._config.get("capture", {})
            self._capture_worker.set_device(device_idx, cv2.CAP_DSHOW)
            self._capture_worker.set_resolution(cap_cfg.get("target_width", 1920), cap_cfg.get("target_height", 1080))
            self._capture_worker.set_fps(cap_cfg.get("target_fps", 30))
        elif source_type == "camera":
            device_idx = self._control_panel.get_device_index()
            cap_cfg = self._config.get("capture", {})
            self._capture_worker.set_camera(device_idx if device_idx is not None else 0)
            self._capture_worker.set_resolution(cap_cfg.get("target_width", 1920), cap_cfg.get("target_height", 1080))
            self._capture_worker.set_fps(cap_cfg.get("target_fps", 30))
        else:
            video_path = self._control_panel.get_video_path()
            if not video_path or not os.path.exists(video_path):
                QMessageBox.warning(self, "文件未选择", "请先选择一个有效的 MP4 视频文件。")
                return
            vf_cfg = self._config.get("video_file", {})
            self._capture_worker.set_video_file(video_path, vf_cfg.get("loop_playback", True))
            self._capture_worker.set_fps(vf_cfg.get("target_fps", 30))

        model_path = self._control_panel.get_model_path()
        if not os.path.exists(model_path):
            QMessageBox.warning(self, "模型文件缺失", f"未找到模型文件:\n{model_path}")
            return
        self._inference_worker.load_model(model_path)

        self._frame_buffer.clear()
        self._lesion_panel.clear()
        self._capture_worker.start()
        self._inference_worker.start()
        self._control_panel.set_running_state(True)

        if source_type == "device":
            self._status_bar.set_device_status(f"运行中 (设备#{self._control_panel.get_device_index()})")
        elif source_type == "camera":
            self._status_bar.set_device_status(f"运行中 (摄像头#{self._control_panel.get_device_index()})")
        else:
            self._status_bar.set_device_status(f"运行中 ({os.path.basename(self._control_panel.get_video_path() or '')})")
        self._logger.info("开始检测")

    def _on_stop(self) -> None:
        self._capture_worker.stop()
        self._inference_worker.stop()
        self._capture_worker.wait(3000)
        self._inference_worker.wait(3000)
        if self._recorder.is_recording:
            self._recorder.stop()
        self._video_widget.clear()
        self._detection_table.clear_detections()
        self._control_panel.set_running_state(False)
        self._status_bar.set_device_status("已停止")
        self._status_bar.set_capture_fps(0)
        self._status_bar.set_inference_fps(0)
        self._status_bar.set_detection_count(0)
        self._logger.info("检测已停止")

    def _on_confidence_changed(self, value: float) -> None:
        self._inference_worker.set_confidence(value)

    def _on_clahe_toggled(self, enabled: bool) -> None:
        self._inference_worker.set_clahe(enabled)
        self._logger.info(f"CLAHE: {'开' if enabled else '关'}")

    def _on_result_ready(self, annotated_frame: np.ndarray, detections: list) -> None:
        self._video_widget.set_frame(annotated_frame)
        self._detection_table.update_detections(detections)
        self._status_bar.set_detection_count(len(detections))
        if self._recorder.is_recording:
            self._recorder.write_frame(annotated_frame)

    def _on_lesion_crops(self, crops: list) -> None:
        for crop_bgr, class_cn, conf in crops:
            self._lesion_panel.add_lesion(crop_bgr, class_cn, conf)

    def _on_screenshot(self) -> None:
        frame = self._video_widget.current_frame
        if frame is None:
            QMessageBox.warning(self, "截图失败", "当前没有可保存的图像帧。")
            return
        path = save_screenshot(frame)
        self._status_bar.showMessage(f"截图已保存: {path}", 3000)
        self._logger.info(f"截图保存: {path}")

    def _on_record_toggle(self, recording: bool) -> None:
        if recording:
            frame = self._video_widget.current_frame
            if frame is None:
                return
            h, w = frame.shape[:2]
            self._recorder.start((w, h))
            self._status_bar.showMessage("开始录制...", 2000)
        else:
            path = self._recorder.stop()
            if path:
                self._status_bar.showMessage(f"录制已保存: {path}", 5000)

    def _on_source_ended(self) -> None:
        self._status_bar.showMessage("视频播放完毕", 3000)

    def _on_capture_error(self, message: str) -> None:
        self._logger.error(f"采集错误: {message}")
        QMessageBox.critical(self, "采集设备错误", message)
        self._on_stop()

    def _on_inference_error(self, message: str) -> None:
        self._logger.error(f"推理错误: {message}")
        QMessageBox.critical(self, "推理错误", message)
        self._on_stop()

    def closeEvent(self, event) -> None:
        self._on_stop()
        self._logger.info("应用程序关闭")
        super().closeEvent(event)
