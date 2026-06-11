"""Общий пул API-ключей: round-robin + ТАЙМИРОВАННАЯ заморозка (анти-шторм).

429/quota → ключ замораживается на длительный срок (до сброса квоты), а НЕ кладётся
в cooldown с авто-очисткой. Если все ключи заморожены — get() возвращает None
(обработка останавливается), вместо бесконечного реюза мёртвого ключа.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Дефолтная заморозка при 429 — сутки (дневная квота Gemini сбрасывается ~раз в день).
QUOTA_FREEZE_SECONDS = 24 * 3600


class SimplePool:
    def __init__(self, keys: list[str], provider: str):
        self.keys = list(keys)
        self.provider = provider
        self._idx = 0
        self._frozen: dict[str, float] = {}  # key -> момент разморозки (unix ts)

    def get(self) -> Optional[str]:
        now = time.time()
        available = [k for k in self.keys if self._frozen.get(k, 0.0) <= now]
        if not available:
            return None  # все заморожены → СТОП (без авто-разморозки)
        key = available[self._idx % len(available)]
        self._idx += 1
        return key

    def freeze(self, key: str, seconds: float) -> None:
        self._frozen[key] = time.time() + seconds
        logger.warning("[Pool:%s] ключ заморожен на %.0fs (до сброса квоты)", self.provider, seconds)

    def report_quota_exceeded(self, key: str, seconds: float = QUOTA_FREEZE_SECONDS) -> None:
        """429 — заморозить ключ до сброса квоты (не на секунды)."""
        self.freeze(key, seconds)

    @property
    def available(self) -> bool:
        now = time.time()
        return any(self._frozen.get(k, 0.0) <= now for k in self.keys)
