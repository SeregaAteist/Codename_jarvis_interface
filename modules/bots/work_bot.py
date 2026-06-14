"""JARVIS Work Bot — рабочие уведомления в топик 202 + inbox-роутинг CRM."""

from __future__ import annotations

import logging
import os
import sys

import httpx
from telegram.ext import Application, MessageHandler, filters

# load .env before any os.getenv calls
from shared.config.secrets import opt as _opt  # noqa: F401

logger = logging.getLogger(__name__)

WORK_TOKEN = os.getenv("JARVIS_WORK_BOT_TOKEN", "")
WORK_CHAT_ID = int(os.getenv("WORK_CHAT_ID") or os.getenv("RAFAIL_CHAT_ID") or 0)
WORK_TOPIC_ID = int(os.getenv("WORK_TOPIC_ID", "202"))


async def send_work(text: str, parse_mode: str = "HTML") -> None:
    """Отправить рабочее уведомление в топик 202 (вызывается извне без polling)."""
    if not WORK_TOKEN or not WORK_CHAT_ID:
        logger.warning("[work-bot] JARVIS_WORK_BOT_TOKEN или WORK_CHAT_ID не заданы")
        return
    payload: dict = {
        "chat_id": WORK_CHAT_ID,
        "message_thread_id": WORK_TOPIC_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"https://api.telegram.org/bot{WORK_TOKEN}/sendMessage", json=payload
        )
        if r.status_code != 200:
            logger.error("[work-bot] TG %s: %s", r.status_code, r.text[:200])


def main() -> None:
    from shared.logging_setup import setup_logging

    setup_logging("~/Projects/jarvis/logs/work-bot.log")
    if not WORK_TOKEN:
        logger.warning("JARVIS_WORK_BOT_TOKEN не задан — выход.")
        sys.exit(0)

    from modules.bots.inbox_dispatcher import dispatch, handle_inbox_voice

    app = Application.builder().token(WORK_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, handle_inbox_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch))
    logger.info("[work-bot] запущен (chat=%d, topic=%d)", WORK_CHAT_ID, WORK_TOPIC_ID)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
