"""Единая настройка логирования: маскировка секретов (S-1) + ротация (S-2).

S-1: httpx по INFO логирует полные URL вида .../bot<token>/getUpdates — это утечка
токена. Понижаем httpx/httpcore до WARNING + фильтр-маска на всех хендлерах
(defense-in-depth: даже если токен/ключ попадёт в сообщение — будет замаскирован).
S-2: RotatingFileHandler 10MB × 5 файлов.
"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Telegram bot token:  <digits>:<35+ base64-ish>  → <id4>***:***
_TOKEN_RE = re.compile(r"(\d{6,10}):[A-Za-z0-9_-]{30,}")
# Gemini/Google API key: AIza...  → AIza****
_AIZA_RE = re.compile(r"AIza[0-9A-Za-z_\-]{6}[0-9A-Za-z_\-]+")
# Anthropic / GitHub / Groq
_GENERIC_RE = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{6}|github_pat_[A-Za-z0-9_]{6}|gsk_[A-Za-z0-9]{6})[A-Za-z0-9_\-]+")


def mask(s: str) -> str:
    s = _TOKEN_RE.sub(lambda m: f"{m.group(1)[:4]}***:***", s)
    s = _AIZA_RE.sub("AIza***", s)
    s = _GENERIC_RE.sub(r"\1***", s)
    return s


class SecretMaskFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = mask(record.msg)
            if record.args:
                record.args = tuple(mask(a) if isinstance(a, str) else a for a in record.args)
        except Exception:
            pass
        return True


def setup_logging(log_file, level: int = logging.INFO, console: bool = True) -> logging.Logger:
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    mask_filter = SecretMaskFilter()

    handlers: list[logging.Handler] = []
    fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(mask_filter)
    handlers.append(fh)
    if console:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        sh.addFilter(mask_filter)
        handlers.append(sh)

    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    for h in handlers:
        root.addHandler(h)

    # S-1: основной фикс утечки — httpx/httpcore не должны логировать URL с токеном.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return root


def setup(name: str, log_dir: str = "~/Projects/jarvis/logs",
          level: int = logging.INFO) -> logging.Logger:
    """Именованный логгер с ротацией и маскировкой — для скриптов вне launchd.

    Сервисы под launchd уже пишут stdout/stderr в logs/*.log (plist),
    им файловый хэндлер НЕ нужен — будет дублирование.
    """
    logs = Path(log_dir).expanduser()
    logs.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return logger  # уже настроен — не плодим хэндлеры

    fh = RotatingFileHandler(logs / f"{name}.log", maxBytes=10 * 1024 * 1024,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    fh.addFilter(SecretMaskFilter())
    logger.addHandler(fh)
    return logger
