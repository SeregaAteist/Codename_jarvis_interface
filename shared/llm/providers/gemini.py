"""Gemini-провайдер (google-genai). ОДНА попытка на вызов.

Анти-шторм: здесь НЕТ внутренней рекурсии/циклов retry — это делает внешний
retry_with_backoff (shared/errors.py). На 429 ключ замораживается в пуле (до сброса
квоты) и ошибка пробрасывается; повтор по 429 не делается. Выбор модели (основная/
fallback) — параметром use_fallback (переключает вызывающий на 503).
"""

from __future__ import annotations

import logging
from typing import Any

from shared.errors import QuotaExhausted, classify
from shared.llm.key_pool import SimplePool

logger = logging.getLogger(__name__)

_SAFETY_CATS = (
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
)


def _text(response: Any) -> str:
    try:
        return str(getattr(response, "text"))
    except Exception as e:
        logger.debug(
            "[gemini] response.text недоступен (%s), извлекаю из candidates", e
        )
        for c in getattr(response, "candidates", []) or []:
            for p in c.content.parts:
                if getattr(p, "text", ""):
                    return str(p.text)
        raise RuntimeError("EMPTY: Gemini вернул пустой ответ")


async def generate(
    model: str,
    contents: Any,
    pool: SimplePool,
    fallback_model: str | None = None,
    max_output_tokens: int | None = None,
    use_fallback: bool = False,
) -> str:
    """Одна попытка генерации. Ключ из пула; на 429 — заморозка + проброс."""
    from google import genai
    from google.genai import types

    key = pool.get()
    if not key:
        raise QuotaExhausted("все ключи Gemini заморожены (квота)")

    use_model = fallback_model if (use_fallback and fallback_model) else model
    safety = [
        types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in _SAFETY_CATS
    ]
    cfg_kw: dict[str, object] = {"safety_settings": safety}
    if max_output_tokens:
        cfg_kw["max_output_tokens"] = max_output_tokens

    client = genai.Client(api_key=key)
    try:
        response = await client.aio.models.generate_content(
            model=use_model,
            contents=contents,
            config=types.GenerateContentConfig(**cfg_kw),
        )
        return _text(response)
    except Exception as e:
        if classify(e) == "GEMINI_429":
            pool.report_quota_exceeded(key)  # заморозка до сброса квоты (анти-шторм)
        raise
