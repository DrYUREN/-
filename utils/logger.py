"""日志配置工具。"""

import logging
import os
from datetime import datetime


def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("胃镜精灵")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)

    ch = logging.StreamHandler()
    ch.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
