"""Ollama-провайдер через HTTP (локальный сервер), без отдельного SDK.

Роль 'local_chat'. Использует httpx + CFG.OLLAMA_HOST (default http://localhost:11434).
"""

from __future__ import annotations

import logging

from shared.config import CFG

logger = logging.getLogger(__name__)


async def generate(model: str, content: str | list[str]) -> str:
    import httpx

    text = content if isinstance(content, str) else "\n".join(map(str, content))
    payload = {"model": model, "prompt": text, "stream": False}
    async with httpx.AsyncClient(timeout=120) as cli:
        try:
            r = await cli.post(f"{CFG.OLLAMA_HOST}/api/generate", json=payload)
            r.raise_for_status()
            return str(r.json().get("response", "")).strip()
        except httpx.HTTPStatusError as e:
            logger.warning("[ollama] HTTP ошибка %d: %s", e.response.status_code, e)
            raise
        except Exception as e:
            logger.error("[ollama] неожиданная ошибка: %s", e)
            raise
