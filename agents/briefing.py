"""BriefingAgent — утренний дайджест: Reddit RSS → Gemini-резюме → Telegram владельцу.

- Сбор по сабреддитам параллельно; ошибка одного не роняет остальные.
- Глобальный таймаут 2 минуты. При 0 постах — всё равно шлёт ("источники недоступны").
- Шлёт владельцу (CFG.OWNER_USER_ID) отдельным Bot-инстансом (не мешает polling).
"""

from __future__ import annotations

import asyncio
import logging
import time

from agents.base import BaseAgent
from agents.registry import register
from core.briefing.formatter import format_briefing
from core.briefing.reddit_rss import fetch_top_posts
from core.briefing.summarizer import summarize_news
from shared.config import CFG
from shared.config import base as cfg_base

logger = logging.getLogger(__name__)

BRIEFING_TIMEOUT = 120  # 2 минуты на всю операцию


@register
class BriefingAgent(BaseAgent):
    name = "briefing"
    capabilities = ["morning_briefing", "news_digest"]

    async def execute(self, task: str) -> str:
        await self.run_briefing()
        return "briefing sent"

    async def run_briefing(self) -> None:
        try:
            await asyncio.wait_for(self._collect_and_send(), timeout=BRIEFING_TIMEOUT)
        except asyncio.TimeoutError:
            logger.error("[briefing] TIMEOUT 2 мин")
            await self._send("🌅 Утренний брифинг: ⏱️ TIMEOUT — превышено время сбора.")
        except Exception as e:  # noqa: BLE001
            logger.error("[briefing] %s", e)

    async def _collect_and_send(self) -> None:
        cfg = cfg_base.load_module_yaml("briefing")
        rcfg = cfg.get("reddit", {})
        subs = rcfg.get("subreddits", ["artificial", "MachineLearning", "LocalLLaMA"])
        limit = int(rcfg.get("limit", 5))
        hours = int(rcfg.get("hours", 24))
        deadline = time.time() + BRIEFING_TIMEOUT - 5

        results = await asyncio.gather(
            *(fetch_top_posts(s, limit, hours) for s in subs), return_exceptions=True
        )
        posts: list[dict] = []
        for r in results:
            if isinstance(r, list):
                posts.extend(r)

        if posts:
            summary = await summarize_news(posts, deadline_ts=deadline)
            msg = format_briefing(summary, len(posts))
        else:
            msg = format_briefing("⚠️ Источники недоступны (Reddit не ответил).", 0)
        await self._send(msg)
        logger.info("[briefing] отправлено, постов=%d", len(posts))

    async def _send(self, text: str) -> None:
        from telegram import Bot

        bot = Bot(token=CFG.TELEGRAM_TOKEN)
        async with bot:
            await bot.send_message(chat_id=CFG.OWNER_USER_ID, text=text)
