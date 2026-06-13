"""Карта ошибок + retry-политика (общая для всех провайдеров).

Принципы:
- В ЧАТ — только короткое русское сообщение из ERROR_MESSAGES; в ЛОГ — полный код+детали.
- Неизвестная ошибка → "SYS" (никогда сырой JSON/traceback пользователю).
- retry ТОЛЬКО для временных (503/500/NET). 429 НЕ повторяется (заморозка ключа в пуле).
- Экспоненциальный backoff с jitter, глобальный дедлайн (таймаут media) поверх.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

ERROR_MESSAGES: dict[str, str] = {
    "GEMINI_503": "⚠️ 503 — Сервис Gemini перегружен, повторяю автоматически…",
    "GEMINI_429": "⏳ 429 — Дневной лимит исчерпан, обработка возобновится после сброса квоты",
    "GEMINI_500": "⚠️ 500 — Внутренняя ошибка Gemini, повторяю…",
    "GEMINI_400": "⚠️ 400 — Файл не принят (формат или размер), попробуйте другой",
    "TIMEOUT": "⏱️ TIMEOUT — Превышено время обработки, задача отменена",
    "NET": "⚠️ NET — Нет связи с сервером, повторяю…",
    "FILE_DL": "⚠️ FILE — Не удалось скачать файл из Telegram, отправьте ещё раз",
    "MEDIA": "⚠️ MEDIA — Не удалось обработать этот файл, попробуйте другой",
    "EMPTY": "⚠️ EMPTY — Gemini вернул пустой ответ, повторяю…",
    "SAVE": "⚠️ SAVE — Не удалось сохранить, попробуйте ещё раз",
    "SYS": "⚠️ SYS — Внутренняя ошибка, задача сохранена, разработчик уведомлён",
}

# backoff (сек): ~10 минут терпеливых попыток (Google best practice)
DELAYS = [2, 4, 8, 15, 30, 45, 60, 90, 120, 120]
JITTER = 0.2  # ±20%
RETRIABLE = {"GEMINI_503", "GEMINI_500", "NET", "EMPTY"}


class MediaTimeout(Exception):  # noqa: N818
    """Превышен глобальный дедлайн обработки media."""


class QuotaExhausted(Exception):  # noqa: N818
    """Все ключи провайдера заморожены (429) — повторять нельзя."""


def _code(exc: Exception) -> int | None:
    c = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(c, int):
        return c
    m = re.search(r"\b(4\d\d|5\d\d)\b", str(exc))
    return int(m.group(1)) if m else None


def classify(exc: Exception) -> str:
    """Ошибка → код из ERROR_MESSAGES. Неизвестное → 'SYS'."""
    if isinstance(exc, (MediaTimeout, asyncio.TimeoutError)):
        return "TIMEOUT"
    if isinstance(exc, QuotaExhausted):
        return "GEMINI_429"
    s = str(exc).lower()
    code = _code(exc)
    if code == 429 or "quota" in s or "resource_exhausted" in s or "rate limit" in s:
        return "GEMINI_429"
    if code == 503 or "overloaded" in s or "unavailable" in s:
        return "GEMINI_503"
    if code == 500 or "internal error" in s:
        return "GEMINI_500"
    if code == 400 or "invalid argument" in s or "failed_precondition" in s:
        return "GEMINI_400"
    name = type(exc).__name__.lower()
    if "connection" in s or any(
        x in name
        for x in ("connect", "timeout", "network", "socket", "httpx", "readerror")
    ):
        return "NET"
    if "empty" in s or "no text" in s:
        return "EMPTY"
    return "SYS"


def is_retriable(code: str) -> bool:
    return code in RETRIABLE


def user_message(code: str) -> str:
    return ERROR_MESSAGES.get(code, ERROR_MESSAGES["SYS"])


def message_for(exc: Exception) -> str:
    return user_message(classify(exc))


async def retry_with_backoff(
    attempt: Callable[[], Awaitable[str]],
    *,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    deadline_ts: float | None = None,
    max_attempts: int = 10,
) -> str:
    """Повторять attempt() с backoff+jitter ТОЛЬКО для временных ошибок.

    - 429/400/SYS — не повторяются (re-raise сразу).
    - deadline_ts — жёсткий дедлайн (глобальный таймаут media) поверх backoff.
    - on_progress(text) — редактирование ОДНОГО статус-сообщения (не плодить новые).
    """
    last: Exception | None = None
    for i in range(1, max_attempts + 1):
        if deadline_ts and time.time() >= deadline_ts:
            raise MediaTimeout("media deadline exceeded")
        try:
            return await attempt()
        except Exception as e:  # noqa: BLE001
            last = e
            code = classify(e)
            logger.warning(
                "[retry] %d/%d code=%s detail=%s", i, max_attempts, code, str(e)[:200]
            )
            if not is_retriable(code) or i == max_attempts:
                raise
            delay = DELAYS[min(i - 1, len(DELAYS) - 1)] * (
                1 + random.uniform(-JITTER, JITTER)
            )
            if deadline_ts:
                remain = deadline_ts - time.time()
                if remain <= 0:
                    raise MediaTimeout("media deadline exceeded")
                delay = min(delay, remain)
            if on_progress:
                try:
                    await on_progress(
                        f"{user_message(code)} ({i}/{max_attempts}, ждём {int(delay)}с)"
                    )
                except Exception:
                    pass
            await asyncio.sleep(delay)
    raise last if last else RuntimeError("retry_with_backoff: нет попыток")
