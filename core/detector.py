"""YOLOv8推理工作线程。线条标记、CLAHE预处理、病灶截图提取。"""

import os
import time
from collections import deque

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
from PyQt5.QtCore import QThread, pyqtSignal

from core.frame_buffer import FrameBuffer

# 不同病理类型的线条样式
LINE_STYLES = {
    "cancer": {"color": (0, 0, 255), "thickness": 4, "dash": True},    # 红-虚线-粗
    "ulcer":  {"color": (0, 165, 255), "thickness": 3, "dash": False},  # 橙-实线-中粗
    "polyp":  {"color": (0, 255, 255), "thickness": 3, "dash": False},  # 黄-实线-中粗
    "normal": {"color": (0, 255, 0), "thickness": 2, "dash": False},   # 绿-实线-细
}


def _draw_dashed_rect(img, pt1, pt2, color, thickness, dash_len=15):
    """在图像上绘制虚线矩形框"""
    x1, y1 = pt1
    x2, y2 = pt2
    # 上边
    for x in range(x1, x2, dash_len * 2):
        xe = min(x + dash_len, x2)
        cv2.line(img, (x, y1), (xe, y1), color, thickness)
    # 下边
    for x in range(x1, x2, dash_len * 2):
        xe = min(x + dash_len, x2)
        cv2.line(img, (x, y2), (xe, y2), color, thickness)
    # 左边
    for y in range(y1, y2, dash_len * 2):
        ye = min(y + dash_len, y2)
        cv2.line(img, (x1, y), (x1, ye), color, thickness)
    # 右边
    for y in range(y1, y2, dash_len * 2):
        ye = min(y + dash_len, y2)
        cv2.line(img, (x2, y), (x2, ye), color, thickness)


class InferenceWorker(QThread):
    result_ready = pyqtSignal(np.ndarray, list)    # annotated_frame, detections
    lesion_crops = pyqtSignal(list)                 # [(crop_bgr, class_cn, conf), ...]
    inference_error = pyqtSignal(str)
    inference_fps_update = pyqtSignal(float)

    def __init__(self, frame_buffer: FrameBuffer, config: dict,
                 classes_config: dict, parent=None) -> None:
        super().__init__(parent)
        self._frame_buffer = frame_buffer
        self._config = config
        self._classes_config = classes_config
        self._model: YOLO | None = None
        self._confidence = config["detection"]["confidence_threshold"]
        self._iou = config["detection"]["iou_threshold"]
        self._device = config["detection"]["device"]
        self._half = config["detection"]["half_precision"]
        self._max_size = config["detection"]["max_image_size"]
        self._running = False

        # CLAHE
        pp = config.get("preprocessing", {})
        clahe_cfg = pp.get("clahe", {})
        self._clahe_enabled = clahe_cfg.get("enabled", False)
        self._clahe = cv2.createCLAHE(
            clipLimit=clahe_cfg.get("clip_limit", 2.0),
            tileGridSize=tuple(clahe_cfg.get("tile_grid_size", [8, 8])),
        ) if self._clahe_enabled else None

        # 字体
        font_path = classes_config.get("font", {}).get("face", "C:/Windows/Fonts/simhei.ttf")
        font_scale = classes_config.get("font", {}).get("scale", 0.6)
        try:
            self._font = ImageFont.truetype(font_path, int(22 * font_scale))
        except OSError:
            self._font = ImageFont.load_default()

        self._model_path = ""

    def load_model(self, model_path: str) -> None:
        if not os.path.exists(model_path):
            self.inference_error.emit(f"模型文件不存在: {model_path}")
            return
        try:
            self._model = YOLO(model_path)
            self._model_path = model_path
            if self._device.startswith("cuda"):
                self._model.to(self._device)
        except Exception as e:
            self.inference_error.emit(f"模型加载失败: {e}")

    def set_confidence(self, threshold: float) -> None:
        self._confidence = threshold

    def set_iou(self, threshold: float) -> None:
        self._iou = threshold

    def set_clahe(self, enabled: bool, clip_limit: float = 2.0,
                  tile_size: tuple = (8, 8)) -> None:
        self._clahe_enabled = enabled
        if enabled:
            self._clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
        else:
            self._clahe = None

    def run(self) -> None:
        if self._model is None:
            model_path = self._config["detection"]["model_path"]
            self.load_model(model_path)

        if self._model is None:
            self.inference_error.emit("模型未加载，无法启动推理。")
            return

        warmup = self._config.get("inference", {}).get("warmup_iterations", 3)
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        for _ in range(warmup):
            self._model.predict(dummy, conf=0.5, iou=0.45, device=self._device,
                                half=self._half, imgsz=self._max_size, verbose=False)

        self._running = True
        timestamps = deque(maxlen=30)

        while self._running:
            frame = self._frame_buffer.get_latest()
            if frame is None:
                self.msleep(5)
                continue

            try:
                input_frame = self._preprocess(frame)
                results = self._model.predict(
                    input_frame, conf=self._confidence, iou=self._iou,
                    device=self._device, half=self._half,
                    imgsz=self._max_size, verbose=False,
                )
            except Exception as e:
                self.inference_error.emit(f"推理异常: {e}")
                continue

            annotated, lesion_imgs = self._draw_results(frame, results[0])
            detections = self._extract_detections(results[0])
            self.result_ready.emit(annotated, detections)
            if lesion_imgs:
                self.lesion_crops.emit(lesion_imgs)

            now = time.time()
            timestamps.append(now)
            if len(timestamps) >= 2:
                fps_val = len(timestamps) / (timestamps[-1] - timestamps[0])
                self.inference_fps_update.emit(round(fps_val, 1))

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        if not self._clahe_enabled or self._clahe is None:
            return frame
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _draw_results(self, frame: np.ndarray, result) -> tuple[np.ndarray, list]:
        """线条标记 + PIL中文标签 + 提取病灶截图"""
        annotated = frame.copy()
        lesion_imgs = []
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return annotated, lesion_imgs

        # 第一遍：画矩形框 + 提取病灶截图，收集标签数据
        labels_data = []

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            cls_info = self._classes_config["classes"].get(cls_id)
            if cls_info is None:
                continue

            group = cls_info.get("group", "normal")
            style = LINE_STYLES.get(group, LINE_STYLES["normal"])
            color = style["color"]
            thickness = style["thickness"]

            # 线条标记 (画在 OpenCV annotated 上)
            if style.get("dash"):
                _draw_dashed_rect(annotated, (x1, y1), (x2, y2), color, thickness)
            else:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

            label = f"{cls_info['name_cn']} {conf:.2f}"
            labels_data.append((x1, y1, label, color))

            # 提取病灶截图
            pad = 20
            cy1 = max(0, y1 - pad)
            cy2 = min(frame.shape[0], y2 + pad)
            cx1 = max(0, x1 - pad)
            cx2 = min(frame.shape[1], x2 + pad)
            crop = frame[cy1:cy2, cx1:cx2].copy()
            if crop.size > 0:
                lx1, ly1 = x1 - cx1, y1 - cy1
                lx2, ly2 = x2 - cx1, y2 - cy1
                cv2.rectangle(crop, (lx1, ly1), (lx2, ly2), color, thickness)

                # 缩略图标签
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                crop_pil = Image.fromarray(crop_rgb)
                crop_draw = ImageDraw.Draw(crop_pil)
                color_rgb = (color[2], color[1], color[0])
                cbbox = crop_draw.textbbox((0, 0), label, font=self._font)
                ctw, cth = cbbox[2] - cbbox[0], cbbox[3] - cbbox[1]
                crop_draw.rectangle(
                    [(lx1, max(0, ly1 - cth - 8)), (lx1 + ctw + 8, max(0, ly1))],
                    fill=(0, 0, 0)
                )
                crop_draw.text((lx1 + 4, max(0, ly1 - cth - 4)), label, fill=color_rgb, font=self._font)
                crop = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)
                lesion_imgs.append((crop, cls_info["name_cn"], conf))

        # 第二遍：PIL 中文标签（在已有矩形框的 annotated 上绘制）
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(annotated_rgb)
        draw = ImageDraw.Draw(pil_img)

        for x1, y1, label, color in labels_data:
            color_rgb = (color[2], color[1], color[0])
            bbox = draw.textbbox((0, 0), label, font=self._font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad_x, pad_y = 6, 4
            label_x1, label_y1_r = x1, max(0, y1 - th - pad_y * 2)
            label_x2, label_y2_r = x1 + tw + pad_x * 2, label_y1_r + th + pad_y * 2

            overlay = Image.new('RGBA', pil_img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [(label_x1, label_y1_r), (label_x2, label_y2_r)],
                fill=(0, 0, 0, 160)
            )
            pil_img = Image.alpha_composite(pil_img.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(pil_img)
            draw.text((label_x1 + pad_x, label_y1_r + pad_y), label, fill=color_rgb, font=self._font)

        annotated = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return annotated, lesion_imgs

    def _extract_detections(self, result) -> list[dict]:
        detections = []
        boxes = result.boxes
        if boxes is None:
            return detections
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            cls_info = self._classes_config["classes"].get(cls_id)
            name_cn = cls_info["name_cn"] if cls_info else f"类别{cls_id}"
            group = cls_info.get("group", "unknown") if cls_info else "unknown"
            severity = cls_info.get("severity", 0) if cls_info else 0
            detections.append({
                "class_id": cls_id, "class_cn": name_cn,
                "group": group, "severity": severity,
                "confidence": conf, "bbox": [x1, y1, x2, y2],
            })
        return detections

    def stop(self) -> None:
        self._running = False
