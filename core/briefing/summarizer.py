"""Резюме AI-новостей через LLM-роутер (роль quick_analysis → gemini-2.5-flash)."""
from __future__ import annotations

import logging

from shared.llm import router

logger = logging.getLogger(__name__)

_PROMPT = """Ты составляешь утренний дайджест AI-новостей для технического руководителя.

Вот посты из Reddit за последние 24 часа:
{posts_text}

Составь краткий дайджест:
- 3-5 самых важных тем
- Каждая тема: 1-2 предложения, суть + почему важно
- Язык: русский
- Тон: деловой, без воды
- Формат: маркированный список

Только дайджест, без вступлений и заключений."""


async def summarize_news(posts: list[dict], deadline_ts: float | None = None) -> str:
    if not posts:
        return "Новостей за последние 24ч не найдено."
    posts_text = "\n".join(f"- [{p['subreddit']}] {p['title']}" for p in posts)
    prompt = _PROMPT.format(posts_text=posts_text)
    try:
        return await router.generate("quick_analysis", [prompt], deadline_ts=deadline_ts)
    except Exception as e:
        from shared.errors import message_for
        logger.error("[summarizer] %s", e)
        return message_for(e)  # короткое сообщение из карты, не сырой JSON
