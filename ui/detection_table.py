"""实时检测结果表格。显示类别、置信度、严重程度、位置。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView


SEVERITY_LABELS = {0: "正常", 1: "低", 2: "中", 3: "高"}
SEVERITY_COLORS = {
    0: QColor(0, 200, 0),
    1: QColor(200, 200, 0),
    2: QColor(255, 140, 0),
    3: QColor(255, 50, 50),
}


class DetectionResultTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["类别", "置信度", "程度", "位置"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setMinimumHeight(120)
        self.setColumnWidth(2, 50)

    def update_detections(self, detections: list[dict]) -> None:
        self.setRowCount(len(detections))
        for row, det in enumerate(detections):
            # 类别名
            name = QTableWidgetItem(det["class_cn"])
            name.setForeground(QColor(255, 255, 255))

            # 置信度
            conf = QTableWidgetItem(f"{det['confidence']:.1%}")
            conf.setTextAlignment(Qt.AlignCenter)

            # 严重程度
            severity = det.get("severity", 0)
            sev_text = SEVERITY_LABELS.get(severity, "--")
            sev_item = QTableWidgetItem(sev_text)
            sev_item.setTextAlignment(Qt.AlignCenter)
            sev_item.setForeground(QBrush(SEVERITY_COLORS.get(severity, QColor(128, 128, 128))))

            # 位置
            bbox = det["bbox"]
            loc = QTableWidgetItem(f"({bbox[0]}, {bbox[1]}) - ({bbox[2]}, {bbox[3]})")
            loc.setTextAlignment(Qt.AlignCenter)

            self.setItem(row, 0, name)
            self.setItem(row, 1, conf)
            self.setItem(row, 2, sev_item)
            self.setItem(row, 3, loc)

    def clear_detections(self) -> None:
        self.setRowCount(0)
