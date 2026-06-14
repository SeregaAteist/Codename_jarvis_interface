"""Событийная шина: async pub/sub, in-process, без внешних зависимостей.

Размещена в существующей заготовке core/bus/ (была пустой директорией).
Падение одного подписчика не роняет остальных (gather с return_exceptions).
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[None]]
_subs: dict[str, list[Handler]] = defaultdict(list)


def on(event: str, callback: Handler) -> None:
    """Подписаться на событие."""
    _subs[event].append(callback)


def off(event: str, callback: Handler) -> None:
    """Отписаться (если был подписан)."""
    if callback in _subs.get(event, []):
        _subs[event].remove(callback)


async def emit(event: str, data: dict | None = None) -> None:
    """Опубликовать событие всем подписчикам параллельно."""
    data = data or {}
    handlers = list(_subs.get(event, []))
    if not handlers:
        return
    results = await asyncio.gather(
        *(cb(data) for cb in handlers), return_exceptions=True
    )
    for r in results:
        if isinstance(r, Exception):
            logger.warning("[bus] подписчик события '%s' упал: %s", event, r)


def clear() -> None:
    """Сбросить все подписки (для тестов)."""
    _subs.clear()
