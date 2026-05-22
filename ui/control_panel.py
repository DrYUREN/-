"""控制面板。数据源、模型选择、播放控制、检测参数、截图/录制。"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QComboBox,
    QPushButton, QSlider, QLabel, QHBoxLayout,
    QFileDialog, QCheckBox, QRadioButton, QButtonGroup,
)

SPEED_PRESETS = {"0.25x": 0.25, "0.5x": 0.5, "0.75x": 0.75, "1x": 1.0,
                 "1.5x": 1.5, "2x": 2.0, "3x": 3.0, "4x": 4.0}


class ControlPanel(QWidget):
    # 数据源
    device_changed = pyqtSignal(int)
    video_file_selected = pyqtSignal(str)
    source_type_changed = pyqtSignal(str)
    # 运行
    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    # 播放控制
    pause_toggled = pyqtSignal()
    speed_changed = pyqtSignal(float)
    seek_changed = pyqtSignal(float)        # 进度条拖动 (0.0~1.0)
    # 模型
    model_file_selected = pyqtSignal(str)
    # 检测参数
    confidence_changed = pyqtSignal(float)
    clahe_toggled = pyqtSignal(bool)
    # 保存
    screenshot_clicked = pyqtSignal()
    record_toggled = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(320)
        self._recording = False
        self._paused = False
        self._current_source = "device"
        self._seek_dragging = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # === 数据源 ===
        src = QGroupBox("数据源")
        sl = QVBoxLayout(src)
        self._source_device_btn = QRadioButton("HDMI 采集卡")
        self._source_camera_btn = QRadioButton("电脑摄像头")
        self._source_file_btn = QRadioButton("MP4 视频文件")
        self._source_device_btn.setChecked(True)
        self._source_group = QButtonGroup(self)
        self._source_group.addButton(self._source_device_btn, 0)
        self._source_group.addButton(self._source_camera_btn, 1)
        self._source_group.addButton(self._source_file_btn, 2)
        self._source_group.buttonClicked.connect(self._on_source_changed)
        sl.addWidget(self._source_device_btn)
        sl.addWidget(self._source_camera_btn)
        sl.addWidget(self._source_file_btn)

        # 采集卡设备下拉
        self._device_combo = QComboBox()
        self._device_combo.currentIndexChanged.connect(lambda idx: self.device_changed.emit(idx))
        sl.addWidget(self._device_combo)

        # 摄像头设备下拉
        self._camera_combo = QComboBox()
        self._camera_combo.addItem("摄像头 #0", 0)
        self._camera_combo.addItem("摄像头 #1", 1)
        self._camera_combo.addItem("摄像头 #2", 2)
        self._camera_combo.setVisible(False)
        sl.addWidget(self._camera_combo)

        # 文件选择
        self._file_label = QLabel("未选择文件")
        self._file_label.setStyleSheet("color: #888; font-size: 11px;")
        self._file_label.setWordWrap(True)
        self._file_label.setVisible(False)
        self._browse_btn = QPushButton("浏览...")
        self._browse_btn.clicked.connect(self._on_browse_file)
        self._browse_btn.setVisible(False)
        fl = QHBoxLayout()
        fl.addWidget(self._browse_btn)
        fl.addWidget(self._file_label, 1)
        sl.addLayout(fl)

        self._refresh_btn = QPushButton("刷新设备列表")
        self._refresh_btn.setToolTip("重新枚举采集设备")
        sl.addWidget(self._refresh_btn)
        layout.addWidget(src)

        # === 模型选择 ===
        model = QGroupBox("模型选择")
        ml = QVBoxLayout(model)
        self._model_label = QLabel("models/best.pt")
        self._model_label.setStyleSheet("color: #4a9eff; font-size: 11px;")
        self._model_label.setWordWrap(True)
        ml.addWidget(self._model_label)
        mb = QPushButton("选择模型文件...")
        mb.clicked.connect(self._on_browse_model)
        ml.addWidget(mb)
        layout.addWidget(model)

        # === 运行控制 ===
        run = QGroupBox("运行控制")
        rl = QVBoxLayout(run)
        bl = QHBoxLayout()
        self._start_btn = QPushButton("开始")
        self._start_btn.setStyleSheet("QPushButton{background:#27ae60;color:#fff;font-weight:bold;padding:6px;border-radius:4px} QPushButton:hover{background:#2ecc71} QPushButton:disabled{background:#555}")
        self._start_btn.clicked.connect(self.start_clicked.emit)
        self._stop_btn = QPushButton("停止")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet("QPushButton{background:#c0392b;color:#fff;font-weight:bold;padding:6px;border-radius:4px} QPushButton:hover{background:#e74c3c} QPushButton:disabled{background:#555}")
        self._stop_btn.clicked.connect(self.stop_clicked.emit)
        bl.addWidget(self._start_btn)
        bl.addWidget(self._stop_btn)
        rl.addLayout(bl)

        # 暂停 + 速度
        pbl = QHBoxLayout()
        self._pause_btn = QPushButton("暂停 ⏸")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        self._pause_btn.setStyleSheet("QPushButton:disabled{background:#555;color:#666}")
        pbl.addWidget(self._pause_btn)

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(list(SPEED_PRESETS.keys()))
        self._speed_combo.setCurrentText("1x")
        self._speed_combo.setEnabled(False)
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
        pbl.addWidget(self._speed_combo)
        rl.addLayout(pbl)

        # 进度条 (仅MP4模式)
        self._progress_slider = QSlider(Qt.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setEnabled(False)
        self._progress_slider.setVisible(False)
        self._progress_slider.sliderPressed.connect(self._on_seek_pressed)
        self._progress_slider.sliderReleased.connect(self._on_seek_released)
        self._progress_label = QLabel("00:00 / 00:00")
        self._progress_label.setStyleSheet("color: #888; font-size: 10px;")
        self._progress_label.setAlignment(Qt.AlignCenter)
        self._progress_label.setVisible(False)
        rl.addWidget(self._progress_slider)
        rl.addWidget(self._progress_label)
        layout.addWidget(run)

        # === 检测参数 ===
        det = QGroupBox("检测参数")
        dl = QVBoxLayout(det)
        self._conf_label = QLabel("置信度: 0.50")
        dl.addWidget(self._conf_label)
        self._conf_slider = QSlider(Qt.Horizontal)
        self._conf_slider.setRange(1, 99)
        self._conf_slider.setValue(50)
        self._conf_slider.setTickPosition(QSlider.TicksBelow)
        self._conf_slider.setTickInterval(10)
        self._conf_slider.valueChanged.connect(self._on_confidence_changed)
        dl.addWidget(self._conf_slider)
        self._clahe_check = QCheckBox("CLAHE 图像增强")
        self._clahe_check.toggled.connect(self.clahe_toggled.emit)
        dl.addWidget(self._clahe_check)
        layout.addWidget(det)

        # === 保存 ===
        save = QGroupBox("图像保存")
        svl = QVBoxLayout(save)
        self._screenshot_btn = QPushButton("截图保存")
        self._screenshot_btn.setEnabled(False)
        self._screenshot_btn.clicked.connect(self.screenshot_clicked.emit)
        svl.addWidget(self._screenshot_btn)
        self._record_btn = QPushButton("开始录制")
        self._record_btn.setEnabled(False)
        self._record_btn.clicked.connect(self._on_record_toggle)
        svl.addWidget(self._record_btn)
        layout.addWidget(save)
        layout.addStretch()

    # === 事件处理 ===
    def _on_source_changed(self, btn):
        idx = self._source_group.id(btn)
        if idx == 0:
            self._current_source = "device"
        elif idx == 1:
            self._current_source = "camera"
        else:
            self._current_source = "file"

        self._device_combo.setVisible(idx == 0)
        self._camera_combo.setVisible(idx == 1)
        self._browse_btn.setVisible(idx == 2)
        self._file_label.setVisible(idx == 2)
        self._refresh_btn.setVisible(idx == 0)
        self._progress_slider.setVisible(idx == 2)
        self._progress_label.setVisible(idx == 2)
        self.source_type_changed.emit(self._current_source)

    def _on_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", "视频文件 (*.mp4 *.avi *.mov *.mkv);;所有文件 (*.*)")
        if path:
            self._file_label.setText(path)
            self._file_label.setStyleSheet("color: #4a9eff; font-size: 11px;")
            self.video_file_selected.emit(path)

    def _on_browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "models", "模型文件 (*.pt *.pth);;所有文件 (*.*)")
        if path:
            self._model_label.setText(path)
            self._model_label.setStyleSheet("color: #4a9eff; font-size: 11px;")
            self.model_file_selected.emit(path)

    def _on_pause_clicked(self):
        self._paused = not self._paused
        self._pause_btn.setText("继续 ▶" if self._paused else "暂停 ⏸")
        self.pause_toggled.emit()

    def _on_speed_changed(self, text):
        if text in SPEED_PRESETS:
            self.speed_changed.emit(SPEED_PRESETS[text])

    def _on_confidence_changed(self, value):
        conf = value / 100.0
        self._conf_label.setText(f"置信度: {conf:.2f}")
        self.confidence_changed.emit(conf)

    def _on_seek_pressed(self):
        self._seek_dragging = True

    def _on_seek_released(self):
        self._seek_dragging = False
        pos = self._progress_slider.value() / 1000.0
        self.seek_changed.emit(pos)

    def _on_record_toggle(self):
        self._recording = not self._recording
        if self._recording:
            self._record_btn.setText("停止录制")
            self._record_btn.setStyleSheet("QPushButton{background:#e74c3c;color:#fff;font-weight:bold;padding:6px;border-radius:4px} QPushButton:hover{background:#c0392b}")
        else:
            self._record_btn.setText("开始录制")
            self._record_btn.setStyleSheet("")
        self.record_toggled.emit(self._recording)

    # === 接口方法 ===
    def populate_devices(self, devices: list[dict]):
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        for d in devices:
            self._device_combo.addItem(d["name"], d["index"])
        if devices:
            self._device_combo.setCurrentIndex(0)
        self._device_combo.blockSignals(False)

    def update_progress(self, pos: int, total: int, elapsed_ms: int = 0, duration_ms: int = 0) -> None:
        """更新进度条 (由主线程调用)"""
        if self._seek_dragging:
            return
        self._progress_slider.blockSignals(True)
        if total > 0:
            self._progress_slider.setValue(int(pos / total * 1000))
        else:
            self._progress_slider.setValue(0)
        self._progress_slider.blockSignals(False)

        def _fmt(ms):
            s = ms // 1000
            return f"{s//60:02d}:{s%60:02d}"
        self._progress_label.setText(f"{_fmt(elapsed_ms)} / {_fmt(duration_ms)}")

    def set_running_state(self, running: bool):
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._screenshot_btn.setEnabled(running)
        self._record_btn.setEnabled(running)
        self._pause_btn.setEnabled(running)
        self._speed_combo.setEnabled(running)
        self._device_combo.setEnabled(not running)
        self._camera_combo.setEnabled(not running)
        self._browse_btn.setEnabled(not running)
        self._refresh_btn.setEnabled(not running)
        self._source_device_btn.setEnabled(not running)
        self._source_camera_btn.setEnabled(not running)
        self._source_file_btn.setEnabled(not running)
        is_file = self._current_source == "file"
        self._progress_slider.setEnabled(running and is_file)
        if not running:
            self._progress_slider.setValue(0)
            self._progress_label.setText("00:00 / 00:00")
            self._pause_btn.setText("暂停 ⏸")
            self._paused = False

    def get_confidence(self) -> float:
        return self._conf_slider.value() / 100.0

    def get_device_index(self) -> int | None:
        if self._current_source == "device":
            return self._device_combo.currentData()
        if self._current_source == "camera":
            return self._camera_combo.currentData()
        return None

    def get_video_path(self) -> str | None:
        if self._current_source == "file":
            txt = self._file_label.text()
            return txt if txt != "未选择文件" else None
        return None

    def get_source_type(self) -> str:
        return self._current_source

    def get_model_path(self) -> str:
        return self._model_label.text()

    def set_model_path(self, path: str):
        self._model_label.setText(path)
        self._model_label.setStyleSheet("color: #4a9eff; font-size: 11px;")

    def set_refresh_callback(self, callback):
        self._refresh_btn.clicked.connect(callback)
