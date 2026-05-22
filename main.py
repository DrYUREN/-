"""胃镜精灵 - YOLOv8 胃镜图像实时识别系统入口"""

import sys
import os

os.environ["YOLO_VERBOSE"] = "false"

# PyInstaller 打包后资源在 sys._MEIPASS，开发模式用脚本所在目录
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = sys._MEIPASS
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 必须先导入 ultralytics/torch，再导入 PyQt5（两者 DLL 有冲突，顺序反了 torch 会加载失败）
# PyInstaller 打包后需要将 torch DLL 目录加入搜索路径，确保优先加载
if getattr(sys, 'frozen', False):
    _torch_lib = os.path.join(sys._MEIPASS, 'torch', 'lib')
    if os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)

from ultralytics import YOLO  # noqa: F401

import yaml
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont


def load_config(path: str = "config/settings.yaml") -> dict:
    config_path = os.path.join(PROJECT_ROOT, path)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_classes(path: str = "config/classes.yaml") -> dict:
    classes_path = os.path.join(PROJECT_ROOT, path)
    with open(classes_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    from utils.logger import setup_logger
    logger = setup_logger()
    logger.info("胃镜精灵 启动中...")

    config = load_config()
    classes_config = load_classes("config/classes_1class.yaml")

    # 将相对路径转为绝对路径（相对于项目根目录）
    model_path = config.get("detection", {}).get("model_path", "")
    if model_path and not os.path.isabs(model_path):
        config["detection"]["model_path"] = os.path.join(PROJECT_ROOT, model_path)

    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    from ui.main_window import MainWindow
    window = MainWindow(config, classes_config)
    window.show()

    logger.info("主窗口已显示")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
