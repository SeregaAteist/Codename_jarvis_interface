"""JARVIS Notify — только отправка срочных уведомлений владельцу."""
from __future__ import annotations

import os

from telegram import Bot

_bot: Bot | None = None


async def get_bot() -> Bot:
    global _bot
    if not _bot:
        token = os.getenv("JARVIS_NOTIFY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        _bot = Bot(token=token)
    return _bot


async def send_urgent(text: str, parse_mode: str = "HTML") -> None:
    bot = await get_bot()
    owner_id = int(os.getenv("OWNER_USER_ID", "374728252"))
    await bot.send_message(chat_id=owner_id, text=text,
                           parse_mode=parse_mode,
                           disable_web_page_preview=True)
