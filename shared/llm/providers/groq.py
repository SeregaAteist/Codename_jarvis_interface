"""Groq-провайдер через HTTP (OpenAI-совместимый endpoint), без отдельного SDK.

Роль 'recommend'. Использует httpx (уже в зависимостях) — groq-SDK не требуется.
"""
from __future__ import annotations

import logging

from shared.config import CFG

logger = logging.getLogger(__name__)

_URL = "https://api.groq.com/openai/v1/chat/completions"


async def generate(model: str, content, max_tokens: int = 1024) -> str:
    if not CFG.GROQ_API_KEY:
        return "⚠️ Groq недоступен — нет GROQ_API_KEY в .env"
    import httpx

    text = content if isinstance(content, str) else "\n".join(map(str, content))
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": text}],
    }
    headers = {"Authorization": f"Bearer {CFG.GROQ_API_KEY}"}
    async with httpx.AsyncClient(timeout=60) as cli:
        try:
            r = await cli.post(_URL, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 429:
                logger.warning("[groq] rate limit 429, ключ следует заморозить")
            elif code >= 500:
                logger.warning("[groq] сервис недоступен %d: %s", code, e)
            else:
                logger.error("[groq] HTTP ошибка %d: %s", code, e)
            raise
        except Exception as e:
            logger.error("[groq] неожиданная ошибка: %s", e)
            raise
