"""Общий пул API-ключей с round-robin и cooldown.

Перенесён из modules/tg-media-analyzer/pool/api_pool.py (теперь общий для всех ботов).
Старый путь оставлен тонким shim'ом для обратной совместимости до Фазы 9.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SimplePool:
    def __init__(self, keys: list[str], provider: str):
        self.keys = list(keys)
        self.provider = provider
        self._idx = 0
        self._cooldown: set[str] = set()

    def get(self) -> Optional[str]:
        available = [k for k in self.keys if k not in self._cooldown]
        if not available:
            self._cooldown.clear()
            available = self.keys
        if not available:
            return None
        key = available[self._idx % len(available)]
        self._idx += 1
        return key

    def report_quota_exceeded(self, key: str) -> None:
        self._cooldown.add(key)
        logger.warning("[Pool:%s] key moved to cooldown", self.provider)

    @property
    def available(self) -> bool:
        return bool(self.keys)
