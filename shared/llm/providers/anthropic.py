"""Claude-провайдер (anthropic SDK). Роль 'architect'.

ВНИМАНИЕ: на 11.06.2026 claude-ключ в .env невалиден (401). Провайдер готов,
но роль architect заработает только с валидным ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import asyncio
import logging

from shared.config import CFG

logger = logging.getLogger(__name__)


async def generate(model: str, content, max_tokens: int = 2048) -> str:
    if not CFG.CLAUDE_KEYS:
        return "⚠️ Claude недоступен — нет ANTHROPIC_API_KEY в .env"
    import anthropic

    client = anthropic.Anthropic(api_key=CFG.CLAUDE_KEYS[0])
    text = content if isinstance(content, str) else "\n".join(map(str, content))

    def _call():
        resp = client.messages.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": text}],
        )
        return resp.content[0].text

    return await asyncio.to_thread(_call)
