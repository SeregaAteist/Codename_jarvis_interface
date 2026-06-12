"""Единая настройка логирования JARVIS.

Сервисы под launchd уже пишут stdout/stderr в logs/*.log (plist),
поэтому подключать файловый хэндлер им НЕ нужно — будет дублирование.
setup() — для скриптов/процессов, запускаемых вне launchd.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"


def setup(name: str, log_dir: str = "~/Projects/jarvis/logs",
          level: int = logging.INFO) -> logging.Logger:
    logs = Path(log_dir).expanduser()
    logs.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if any(isinstance(h, logging.handlers.RotatingFileHandler)
           for h in logger.handlers):
        return logger  # уже настроен — не плодим хэндлеры

    fh = logging.handlers.RotatingFileHandler(
        logs / f"{name}.log", maxBytes=10 * 1024 * 1024, backupCount=3)
    fh.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(fh)
    return logger
