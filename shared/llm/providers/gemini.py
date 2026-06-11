"""Gemini-провайдер (google-genai). Ключ при создании Client, ротация через пул.

Ротация = новый Client(api_key=next_key) на каждый вызов (паттерн нового SDK).
На 429/quota — ключ в cooldown и повтор; на 503/overloaded — фоллбэк-модель.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SAFETY_CATS = (
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
)


def _text(response) -> str:
    try:
        return response.text
    except Exception:
        for c in getattr(response, "candidates", []) or []:
            for p in c.content.parts:
                if getattr(p, "text", ""):
                    return p.text
        return "⚠️ Gemini вернул пустой ответ"


async def generate(model: str, contents, pool, fallback_model: str | None = None,
                   max_output_tokens: int | None = None) -> str:
    """Сгенерировать ответ Gemini. contents — список частей (PIL/строки/File).

    Анти-шторм (Фаза 3, минимально): ОГРАНИЧЕННЫЙ цикл вместо рекурсии.
    - 429/quota: ключ в cooldown, пробуем следующий — не больше числа ключей;
    - 503/overloaded: один фоллбэк на запасную модель.
    Полная политика (backoff+jitter, заморозка до reset_at, без re-upload) — Фаза 5.
    """
    from google import genai
    from google.genai import types

    safety = [types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in _SAFETY_CATS]
    cfg_kw = {"safety_settings": safety}
    if max_output_tokens:
        cfg_kw["max_output_tokens"] = max_output_tokens

    attempts = max(1, len(pool.keys))  # на quota — по числу ключей, не бесконечно
    tried_fallback = False
    last_err: Exception | None = None

    for _ in range(attempts):
        key = pool.get()
        if not key:
            return "⚠️ Gemini недоступен — нет ключей"
        client = genai.Client(api_key=key)
        try:
            response = await client.aio.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(**cfg_kw),
            )
            return _text(response)
        except Exception as e:
            s = str(e).lower()
            last_err = e
            if "quota" in s or "429" in s:
                pool.report_quota_exceeded(key)
                continue  # следующий ключ (ограниченно)
            if ("503" in s or "overloaded" in s) and fallback_model and not tried_fallback \
                    and model != fallback_model:
                logger.warning("[gemini] %s перегружена → фоллбэк %s", model, fallback_model)
                model = fallback_model
                tried_fallback = True
                continue
            raise

    raise last_err if last_err else RuntimeError("gemini: исчерпаны попытки")
