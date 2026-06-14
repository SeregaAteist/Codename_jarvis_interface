"""Groq-провайдер через HTTP (OpenAI-совместимый endpoint), без отдельного SDK.

Роли: 'recommend' (llama-3.3-70b-versatile), 'filter' (llama-3.1-8b-instant).
Использует httpx (уже в зависимостях) — groq-SDK не требуется.
"""

from __future__ import annotations

import logging

from shared.config import CFG

logger = logging.getLogger(__name__)

_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_MODELS = {
    "filter": "llama-3.1-8b-instant",
    "analysis": "llama-3.3-70b-versatile",
}

_DAILY_LIMIT = 14400


class GroqProvider:
    """Groq API провайдер с отслеживанием дневного лимита."""

    def __init__(self) -> None:
        self._api_key = CFG.GROQ_API_KEY
        self._calls_today = 0

    @property
    def is_available(self) -> bool:
        return bool(self._api_key) and self._calls_today < _DAILY_LIMIT

    async def generate(
        self, model_role: str, prompt: str, max_tokens: int = 500
    ) -> str:
        if not self.is_available:
            raise RuntimeError("Groq недоступен")
        model = GROQ_MODELS.get(model_role, GROQ_MODELS["filter"])
        result = await generate(model, prompt, max_tokens)
        self._calls_today += 1
        return result


async def generate(model: str, content: str | list[str], max_tokens: int = 1024) -> str:
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
            return str(r.json()["choices"][0]["message"]["content"])
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
