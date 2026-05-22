"""视频采集工作线程。支持 HDMI 采集卡、电脑摄像头和 MP4 文件，含暂停/调速/进度控制。"""

import time
from collections import deque

import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from core.frame_buffer import FrameBuffer


class CaptureWorker(QThread):
    frame_ready = pyqtSignal()
    capture_error = pyqtSignal(str)
    fps_update = pyqtSignal(float)
    source_ended = pyqtSignal()       # 视频文件播放完毕
    state_changed = pyqtSignal(str)   # "playing" / "paused"
    progress_update = pyqtSignal(int, int, int, int)  # pos, total, elapsed_ms, duration_ms

    def __init__(self, frame_buffer: FrameBuffer, parent=None) -> None:
        super().__init__(parent)
        self._frame_buffer = frame_buffer
        self._device_index = 0
        self._api = cv2.CAP_DSHOW
        self._video_path: str | None = None
        self._source_type = "device"
        self._target_width = 1920
        self._target_height = 1080
        self._target_fps = 30
        self._loop_playback = True
        self._running = False
        self._paused = False
        self._speed = 1.0
        self._seek_target: float | None = None  # 0.0~1.0 进度比例
        self._mutex = QMutex()
        self._seek_mutex = QMutex()
        self._wait_condition = QWaitCondition()

    # --- 采集卡模式 ---
    def set_device(self, device_index: int, api: int = cv2.CAP_DSHOW) -> None:
        self._source_type = "device"
        self._device_index = device_index
        self._api = api
        self._video_path = None

    # --- 摄像头模式 ---
    def set_camera(self, device_index: int = 0) -> None:
        self._source_type = "camera"
        self._device_index = device_index
        self._api = cv2.CAP_DSHOW
        self._video_path = None

    def set_resolution(self, width: int, height: int) -> None:
        self._target_width = width
        self._target_height = height

    # --- 文件模式 ---
    def set_video_file(self, path: str, loop: bool = True) -> None:
        self._source_type = "file"
        self._video_path = path
        self._loop_playback = loop
        self._device_index = -1

    def set_fps(self, fps: float) -> None:
        self._target_fps = fps

    # --- 播放控制 ---
    def pause(self) -> None:
        self._paused = True
        self.state_changed.emit("paused")

    def resume(self) -> None:
        self._paused = False
        self.state_changed.emit("playing")

    def toggle_pause(self) -> bool:
        if self._paused:
            self.resume()
        else:
            self.pause()
        return self._paused

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.25, min(4.0, speed))

    def seek(self, position: float) -> None:
        """跳转到指定进度 (0.0~1.0)"""
        self._seek_mutex.lock()
        self._seek_target = max(0.0, min(1.0, position))
        self._seek_mutex.unlock()

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def wait_condition(self) -> QWaitCondition:
        return self._wait_condition

    @property
    def mutex(self) -> QMutex:
        return self._mutex

    @property
    def source_type(self) -> str:
        return self._source_type

    def run(self) -> None:
        self._running = True

        if self._source_type == "file" and self._video_path:
            cap = cv2.VideoCapture(self._video_path)
            source_label = f"视频文件: {self._video_path}"
        elif self._source_type == "camera":
            cap = cv2.VideoCapture(self._device_index, self._api)
            source_label = f"摄像头 #{self._device_index}"
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._target_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._target_height)
        else:
            cap = cv2.VideoCapture(self._device_index, self._api)
            source_label = f"设备 #{self._device_index}"
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._target_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._target_height)
            cap.set(cv2.CAP_PROP_FPS, self._target_fps)

        if not cap.isOpened():
            self.capture_error.emit(f"无法打开{source_label}，请检查连接或文件路径。")
            return

        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        if actual_fps <= 0 or actual_fps > 120:
            actual_fps = self._target_fps
        video_frame_interval = 1.0 / actual_fps if actual_fps > 0 else 1.0 / 30.0

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_ms = int(total_frames / actual_fps * 1000) if actual_fps > 0 else 0

        timestamps = deque(maxlen=30)
        consecutive_failures = 0
        max_failures = 10
        last_frame_time = time.time()

        while self._running:
            # --- 暂停等待 ---
            while self._paused and self._running:
                self.msleep(50)

            # --- 处理 seek ---
            self._seek_mutex.lock()
            seek_to = self._seek_target
            self._seek_target = None
            self._seek_mutex.unlock()
            if seek_to is not None and self._source_type == "file":
                target_frame = int(seek_to * total_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                last_frame_time = time.time()

            # --- 帧率控制 (文件模式按倍速调节) ---
            if self._source_type == "file":
                interval = video_frame_interval / self._speed
                elapsed = time.time() - last_frame_time
                if elapsed < interval:
                    self.msleep(int((interval - elapsed) * 1000))
                    while time.time() - last_frame_time < interval:
                        pass

            ret, frame = cap.read()
            last_frame_time = time.time()

            if not ret:
                if self._source_type == "file" and self._loop_playback:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        self.capture_error.emit("视频文件无法循环读取。")
                        break
                elif self._source_type == "file":
                    self.source_ended.emit()
                    break
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        self.capture_error.emit("设备断开连接或连续读取失败。")
                        break
                    self.msleep(10)
                    continue

            consecutive_failures = 0
            self._frame_buffer.put(frame)
            self._mutex.lock()
            self._wait_condition.wakeAll()
            self._mutex.unlock()
            self.frame_ready.emit()

            # --- 进度更新 (仅文件模式) ---
            if self._source_type == "file":
                current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                elapsed_ms = int(current_pos / actual_fps * 1000) if actual_fps > 0 else 0
                self.progress_update.emit(current_pos, total_frames, elapsed_ms, duration_ms)

            now = time.time()
            timestamps.append(now)
            if len(timestamps) >= 2:
                fps_val = len(timestamps) / (timestamps[-1] - timestamps[0])
                self.fps_update.emit(round(fps_val, 1))

        cap.release()
        self._frame_buffer.clear()

    def stop(self) -> None:
        self._running = False
        self._resume_internal()

    def _resume_internal(self) -> None:
        self._paused = False
        self._mutex.lock()
        self._wait_condition.wakeAll()
        self._mutex.unlock()
