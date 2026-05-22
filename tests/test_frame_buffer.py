"""FrameBuffer 并发安全测试"""

import threading
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.frame_buffer import FrameBuffer


def test_put_get():
    buf = FrameBuffer()
    assert not buf.has_frame
    assert buf.get_latest() is None

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    buf.put(frame)

    assert buf.has_frame
    result = buf.get_latest()
    assert result is not None
    assert result.shape == (100, 100, 3)


def test_overwrite():
    buf = FrameBuffer()
    f1 = np.ones((10, 10, 3), dtype=np.uint8) * 255
    f2 = np.zeros((10, 10, 3), dtype=np.uint8)

    buf.put(f1)
    buf.put(f2)

    result = buf.get_latest()
    assert result is not None
    assert np.mean(result) == 0.0  # latest frame is f2 (zeros)


def test_clear():
    buf = FrameBuffer()
    buf.put(np.zeros((10, 10, 3), dtype=np.uint8))
    buf.clear()
    assert not buf.has_frame
    assert buf.get_latest() is None


def test_concurrent_access():
    buf = FrameBuffer()
    errors = []
    iterations = 5000

    def writer():
        for i in range(iterations):
            frame = np.full((32, 32, 3), i % 256, dtype=np.uint8)
            buf.put(frame)

    def reader():
        for _ in range(iterations):
            result = buf.get_latest()
            if result is not None and result.shape != (32, 32, 3):
                errors.append(f"wrong shape: {result.shape}")

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"concurrency errors: {errors}"


if __name__ == "__main__":
    test_put_get()
    test_overwrite()
    test_clear()
    test_concurrent_access()
    print("所有 FrameBuffer 测试通过!")
