"""病灶截图面板。右侧显示检测到的病灶缩略图及其标注信息，点击可放大。"""

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGroupBox,
    QFrame, QHBoxLayout, QDialog, QPushButton,
)

MAX_THUMBNAILS = 20
THUMB_SIZE = 260


class ZoomDialog(QDialog):
    """病灶截图放大查看弹窗"""
    def __init__(self, crop_bgr: np.ndarray, class_cn: str, conf: float, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{class_cn} - {conf:.1%}")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("QDialog { background: #0f0f23; }")

        layout = QVBoxLayout(self)

        h, w = crop_bgr.shape[:2]
        max_w, max_h = 900, 700
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            nw, nh = int(w * scale), int(h * scale)
        else:
            nw, nh = w, h
        scaled = cv2.resize(crop_bgr, (nw, nh))
        rgb = cv2.cvtColor(scaled, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, nw, nh, nw * 3, QImage.Format_RGB888)

        img_label = QLabel()
        img_label.setPixmap(QPixmap.fromImage(qimg))
        img_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(img_label, 1)

        info = QLabel(f"{class_cn}  置信度: {conf:.2%}  尺寸: {w}x{h}")
        info.setStyleSheet("color: #4a9eff; font-size: 14px; font-weight: bold; padding: 8px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("QPushButton{background:#2a2a5e;color:#ccc;padding:6px 20px;border-radius:4px} QPushButton:hover{background:#3a3a7e}")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignCenter)


class LesionPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("病灶截图")
        group_layout = QVBoxLayout(group)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: #0f0f23; }")

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setSpacing(6)
        self._container_layout.addStretch()

        self._scroll.setWidget(self._container)
        group_layout.addWidget(self._scroll)

        self._count_label = QLabel("暂无病灶截图")
        self._count_label.setStyleSheet("color: #888; font-size: 12px; padding: 8px;")
        self._count_label.setAlignment(Qt.AlignCenter)
        group_layout.addWidget(self._count_label)

        layout.addWidget(group)
        self._thumbnails: list[QFrame] = []

    def _on_card_clicked(self, crop_bgr: np.ndarray, class_cn: str, conf: float) -> None:
        dlg = ZoomDialog(crop_bgr, class_cn, conf, self)
        dlg.exec_()

    def add_lesion(self, crop_bgr: np.ndarray, class_cn: str, conf: float) -> None:
        h, w = crop_bgr.shape[:2]
        if w > h:
            nw, nh = THUMB_SIZE, int(THUMB_SIZE * h / w)
        else:
            nh, nw = THUMB_SIZE, int(THUMB_SIZE * w / h)
        scaled = cv2.resize(crop_bgr, (nw, nh))
        rgb = cv2.cvtColor(scaled, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, nw, nh, nw * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1a1a3e; border: 1px solid #2a2a5e;
                border-radius: 6px; padding: 4px;
            }
            QFrame:hover {
                border: 1px solid #4a9eff;
                background: #1f1f4e;
            }
        """)
        card.setCursor(Qt.PointingHandCursor)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(4, 4, 4, 4)
        card_layout.setSpacing(2)

        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(img_label)

        text = QLabel(f"{class_cn}  {conf:.1%}")
        text.setAlignment(Qt.AlignCenter)
        text.setStyleSheet("color: #4a9eff; font-size: 13px; font-weight: bold;")
        card_layout.addWidget(text)

        # 点击放大
        card.mousePressEvent = lambda ev, c=crop_bgr, cn=class_cn, cf=conf: self._on_card_clicked(c, cn, cf)

        self._container_layout.insertWidget(0, card)
        self._thumbnails.insert(0, card)

        while len(self._thumbnails) > MAX_THUMBNAILS:
            old = self._thumbnails.pop()
            self._container_layout.removeWidget(old)
            old.deleteLater()

        self._count_label.setText(f"共 {len(self._thumbnails)} 张截图")

    def clear(self) -> None:
        for w in self._thumbnails:
            self._container_layout.removeWidget(w)
            w.deleteLater()
        self._thumbnails.clear()
        self._count_label.setText("暂无病灶截图")
