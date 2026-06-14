"""Шина событий JARVIS — pub/sub между модулями."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)
_subscribers: dict[str, list[Callable]] = defaultdict(list)


def subscribe(event: str, handler: Callable) -> None:
    _subscribers[event].append(handler)


async def publish(event: str, data: Any) -> None:
    for handler in _subscribers.get(event, []):
        try:
            await handler(data)
        except Exception as e:
            logger.error("[bus] %s → %s: %s", event, handler.__name__, e)


# Константы событий
CALL_FINISHED = "call.finished"
CALL_ANALYZED = "call.analyzed"
LEAD_STALE = "kommo.lead_stale"
TASKS_CREATED = "kommo.tasks_created"
CONTENT_READY = "rafail.content_ready"
CONTENT_APPROVED = "rafail.content_approved"
