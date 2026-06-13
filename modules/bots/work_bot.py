"""JARVIS Work Bot — рабочие уведомления в топик 202 + inbox-роутинг CRM."""

from __future__ import annotations

import logging
import os
import sys

import httpx
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# load .env before any os.getenv calls
from shared.config.secrets import opt as _opt  # noqa: F401

logger = logging.getLogger(__name__)

WORK_TOKEN = os.getenv("JARVIS_WORK_BOT_TOKEN", "")
WORK_CHAT_ID = int(os.getenv("WORK_CHAT_ID") or os.getenv("RAFAIL_CHAT_ID") or 0)
WORK_TOPIC_ID = int(os.getenv("WORK_TOPIC_ID", "202"))
INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID", "2"))
OWNER_ID = int(os.getenv("OWNER_USER_ID", "374728252"))

_CRM_KEYWORDS = {"звонок", "дзвінок", "клиент", "сделка", "kommo", "crm", "задача"}


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


async def _on_voice_inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Голосовые в inbox: транскрибируем и обрабатываем как текст."""
    msg = update.message
    if not msg or msg.message_thread_id != INBOX_TOPIC_ID:
        return
    if update.effective_user and update.effective_user.id != OWNER_ID:
        return
    from modules.bots.voice_handler import transcribe_voice

    await msg.reply_text("🎙 Слушаю...")
    text = await transcribe_voice(msg.voice.file_id, ctx.bot.token)
    if not text:
        await msg.reply_text("❌ Не удалось распознать голосовое сообщение")
        return
    await msg.reply_text(f"📝 Распознано: {text}")
    msg.text = text
    await _on_inbox(update, ctx)


async def _on_inbox(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Слушаем inbox (топик 2) — реагируем только на CRM-ключевые слова."""
    msg = update.message
    if not msg or msg.message_thread_id != INBOX_TOPIC_ID:
        return
    if update.effective_user and update.effective_user.id != OWNER_ID:
        return

    text_low = (msg.text or "").lower()
    if any(kw in text_low for kw in _CRM_KEYWORDS):
        await ctx.bot.send_message(
            chat_id=WORK_CHAT_ID,
            message_thread_id=INBOX_TOPIC_ID,
            text="📞 JARVIS Work обрабатывает запрос…",
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if not WORK_TOKEN:
        logger.warning("JARVIS_WORK_BOT_TOKEN не задан — выход.")
        sys.exit(0)

    app = Application.builder().token(WORK_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, _on_voice_inbox))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_inbox))
    logger.info("[work-bot] запущен (chat=%d, topic=%d)", WORK_CHAT_ID, WORK_TOPIC_ID)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
