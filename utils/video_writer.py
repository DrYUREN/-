"""截图与录制工具。"""

import os
from datetime import datetime

import cv2
import numpy as np


class VideoRecorder:
    def __init__(self, output_dir: str = "recordings", fps: float = 30.0,
                 codec: str = "mp4v") -> None:
        self._output_dir = output_dir
        self._fps = fps
        self._codec = codec
        self._writer: cv2.VideoWriter | None = None
        self._recording = False
        self._output_path: str | None = None
        os.makedirs(output_dir, exist_ok=True)

    def start(self, frame_size: tuple[int, int]) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = os.path.join(self._output_dir, f"recording_{ts}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*self._codec)
        self._writer = cv2.VideoWriter(
            self._output_path, fourcc, self._fps,
            (frame_size[0], frame_size[1]),
        )
        self._recording = True

    def write_frame(self, frame_bgr: np.ndarray) -> None:
        if self._writer is not None and self._recording:
            self._writer.write(frame_bgr)

    def stop(self) -> str | None:
        self._recording = False
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        return self._output_path

    @property
    def is_recording(self) -> bool:
        return self._recording


def save_screenshot(frame_bgr: np.ndarray, output_dir: str = "captures") -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(output_dir, f"screenshot_{ts}.png")
    cv2.imwrite(path, frame_bgr)
    return path
