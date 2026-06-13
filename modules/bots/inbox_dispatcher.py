"""Inbox dispatcher — читает топик /2 и маршрутизирует агентам."""
from __future__ import annotations

import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

INBOX_CHAT_ID = int(os.getenv("INBOX_CHAT_ID") or os.getenv("RAFAIL_CHAT_ID") or 0)
INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID") or 2)

ROUTES: dict[str, list[str]] = {
    "rafail":    ["навчання", "курс", "матеріал", "знання", "урок", "обучение"],
    "ringostat": ["звонок", "дзвінок", "клиент", "сделка", "kommo", "crm"],
    "anime":     ["аниме", "аніме", "серия", "тайтл"],
}


def detect_agent(text: str) -> str | None:
    low = text.lower()
    for agent, keywords in ROUTES.items():
        if any(kw in low for kw in keywords):
            return agent
    return None


async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик сообщений из inbox-топика /2."""
    msg = update.message
    if not msg:
        return
    if msg.message_thread_id != INBOX_TOPIC_ID:
        return

    text = msg.text or ""
    logger.info("[inbox] сообщение: %s", text[:100])

    agent = detect_agent(text)

    async def _reply(reply_text: str) -> None:
        await context.bot.send_message(
            chat_id=INBOX_CHAT_ID,
            message_thread_id=INBOX_TOPIC_ID,
            text=reply_text,
        )

    if agent == "rafail":
        await _reply("📚 Рафаил берёт в работу…")
    elif agent == "ringostat":
        await _reply("📞 JARVIS Work обрабатывает запрос…")
    elif agent == "anime":
        await _reply("🎌 Проверяю аниме-мониторинг…")
    else:
        await _reply("🤖 Анализирую запрос…")
