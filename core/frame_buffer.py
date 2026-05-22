"""线程安全的单帧缓冲区。采集线程写入，推理线程读取，永远只保留最新帧。"""

import threading
import numpy as np


class FrameBuffer:
    def __init__(self) -> None:
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._has_frame = threading.Event()

    def put(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame.copy()
            self._has_frame.set()

    def get_latest(self) -> np.ndarray | None:
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def clear(self) -> None:
        with self._lock:
            self._frame = None
            self._has_frame.clear()

    @property
    def has_frame(self) -> bool:
        return self._has_frame.is_set()
