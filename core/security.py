"""Security event logger for Jarvis."""
from __future__ import annotations
import logging
import os
import threading

from core.config_paths import SECURITY_LOG as _SECURITY_LOG
_LOG_FILE = str(_SECURITY_LOG)
os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)

_logger = logging.getLogger("jarvis.security")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False

if not _logger.handlers:
    _fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _logger.addHandler(_fh)

_lock = threading.Lock()


def log_threat(event: str, detail: str, ip: str = "local") -> None:
    with _lock:
        _logger.warning("IP:%s EVENT:%s DETAIL:%s", ip, event, detail)


def log_command(cmd: str, allowed: bool, ip: str = "local") -> None:
    level = logging.INFO if allowed else logging.WARNING
    with _lock:
        _logger.log(level, "IP:%s CMD:%.120s ALLOWED:%s", ip, cmd, allowed)


def log_auth(success: bool, ip: str = "local", path: str = "") -> None:
    if not success:
        with _lock:
            _logger.warning("IP:%s AUTH_FAIL PATH:%s", ip, path)


def log_rate_limit(ip: str, path: str) -> None:
    with _lock:
        _logger.warning("IP:%s RATE_LIMITED PATH:%s", ip, path)


def log_input_violation(reason: str, ip: str = "local") -> None:
    with _lock:
        _logger.warning("IP:%s INPUT_VIOLATION %s", ip, reason)
