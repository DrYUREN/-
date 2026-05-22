"""Windows DirectShow 设备枚举工具。"""

import cv2


def enumerate_capture_devices(max_index: int = 9) -> list[dict]:
    devices: list[dict] = []
    for i in range(max_index):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                backend = cap.getBackendName()
                name = f"{backend} 设备 #{i}"
                devices.append({"index": i, "name": name, "api": "CAP_DSHOW"})
                cap.release()
        except Exception:
            continue
    return devices


def find_device_by_name(devices: list[dict], name_substring: str) -> int | None:
    for d in devices:
        if name_substring.lower() in d["name"].lower():
            return d["index"]
    return None


def get_device_resolutions(device_index: int, api: int = cv2.CAP_DSHOW) -> list[tuple[int, int]]:
    common = [
        (3840, 2160), (1920, 1080), (1280, 720),
        (1024, 768), (800, 600), (640, 480),
    ]
    cap = cv2.VideoCapture(device_index, api)
    if not cap.isOpened():
        return []

    supported = []
    orig_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    orig_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    for w, h in common:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w == w and actual_h == h:
            supported.append((w, h))

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, orig_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, orig_h)
    cap.release()
    return supported if supported else [(int(orig_w), int(orig_h))]
