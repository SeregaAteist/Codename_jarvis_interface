"""AnimeBot — Telegram бот для мониторинга аниме."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from agents.db_agent import (
    add_to_watchlist,
    get_all_snapshot,
    get_watchlist,
    update_watchlist_status,
)
from config import cfg
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from modules.bots.base_bot import JarvisBot

logger = logging.getLogger(__name__)

INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID", "2"))

STATUS_LABELS = {
    "watching": "смотрю",
    "completed": "просмотрено",
    "dropped": "дропнул",
    "planned": "запланировано",
}

SYSTEM_PROMPT = """Ты — Anime консультант JARVIS. Говоришь кратко, по делу, на русском.

Функции управления вотчлистом (используй если нужно):
- Добавить: верни "ACTION:ADD:{название}"
- Статус: верни "ACTION:STATUS:{название}|{watching/completed/dropped/planned}"
- Показать список: верни "ACTION:LIST"
- Новинки: верни "ACTION:NEWS"

Если вопрос про аниме — отвечай как эксперт (сезоны, даты, спешлы, рекомендации).
Если команда — выполни и верни ACTION для обработки.
Если непонятно — уточни одним вопросом.

Вотчлист пользователя: {watchlist}
Каталог (последние 30): {catalog}
"""


class AnimeBot(JarvisBot):
    """Telegram бот для мониторинга аниме."""

    def __init__(self) -> None:
        super().__init__(token=cfg.TELEGRAM_TOKEN, name="anime")

    def register_handlers(self, app: Application) -> None:  # type: ignore[type-arg]
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
        )
        app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))

    def _in_my_topic(self, msg: Any) -> bool:
        """True если сообщение адресовано аниме-боту."""
        if msg.chat.type == "private":
            return True
        thread = msg.message_thread_id or 0
        if cfg.ANIME_TOPIC_ID and thread == cfg.ANIME_TOPIC_ID:
            return True
        if thread == INBOX_TOPIC_ID:
            text = (msg.text or "").lower()
            return text.startswith(("аниме,", "anime,"))
        return False

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(
            "🎌 Anime бот активен. Пишите вопросы или команды текстом или голосом.\n"
            "/help — список возможностей"
        )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(
            "🎌 *Anime бот — возможности:*\n\n"
            "📋 *ВОТЧЛИСТ*\n"
            '- "добавь Слизь в список"\n'
            '- "отметь Берсерк как просмотрено"\n'
            '- "дропнул Блич"\n'
            '- "запланируй Ван Пис"\n'
            '- "что я смотрю?"\n'
            '- "мой список"\n\n'
            "🔍 *ИНФОРМАЦИЯ*\n"
            '- "есть ли спешлы у Слизи?"\n'
            '- "в каком порядке смотреть Судьбу?"\n'
            '- "что похожее на Атаку Титанов?"\n'
            '- "когда выйдет 2 сезон Маги?"\n'
            '- "сколько серий в One Piece?"\n\n'
            "📰 *НОВИНКИ*\n"
            '- "что нового вышло?"\n'
            '- "новинки за неделю"\n'
            "- Уведомления приходят автоматически\n\n"
            "🎙 *ГОЛОС*\n"
            "Все команды работают голосом\n\n"
            "/help — это сообщение",
            parse_mode="Markdown",
        )

    async def _handle_text(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        msg = update.message
        if not msg or not msg.from_user:
            return
        if not self.is_owner(msg.from_user.id):
            return
        if not self._in_my_topic(msg):
            return

        text = (msg.text or "").strip()
        if (msg.message_thread_id or 0) == INBOX_TOPIC_ID:
            text = text[text.index(",") + 1 :].strip()

        thinking = await msg.reply_text("🔍 Думаю...")
        try:
            answer = await self._build_answer(text)
            await thinking.edit_text(answer)
        except Exception as e:
            logger.error("[anime] handle_text error: %s", e)
            await thinking.edit_text(f"❌ Ошибка: {type(e).__name__}: {e}")

    async def _handle_voice(
        self, update: Update, ctx: ContextTypes.DEFAULT_TYPE
    ) -> None:
        msg = update.message
        if not msg or not msg.from_user:
            return
        if not self.is_owner(msg.from_user.id):
            return

        thread = msg.message_thread_id or 0
        if msg.chat.type != "private" and not (
            cfg.ANIME_TOPIC_ID and thread == cfg.ANIME_TOPIC_ID
        ):
            return

        thinking = await msg.reply_text("🎙 Слушаю...")
        try:
            from modules.bots.voice_handler import transcribe_voice

            text = await transcribe_voice(msg.voice.file_id, ctx.bot.token)
            if not text:
                await thinking.edit_text(
                    "❌ Не удалось распознать голосовое сообщение."
                )
                return
            await thinking.edit_text(f"🎙 Распознано: {text}\n\n🔍 Думаю...")
            answer = await self._build_answer(text)
            await thinking.edit_text(answer)
        except Exception as e:
            logger.error("[anime] handle_voice error: %s", e)
            await thinking.edit_text(f"❌ Ошибка: {type(e).__name__}: {e}")

    async def _build_answer(self, text: str) -> str:
        """Вызывает Gemini с контекстом вотчлиста и каталога, возвращает чистый ответ."""
        from shared.llm.providers import gemini as gemini_p
        from shared.llm.router import gemini_pool

        watchlist = [w["title"] for w in get_watchlist()]
        catalog = [a["title"] for a in get_all_snapshot()[-30:]]

        prompt = (
            SYSTEM_PROMPT.format(watchlist=watchlist[:20], catalog=catalog)
            + f"\nЗапрос: {text}"
        )

        answer = await gemini_p.generate("gemini-2.5-flash", prompt, gemini_pool)

        if "ACTION:ADD:" in answer:
            title = answer.split("ACTION:ADD:")[1].split("\n")[0].strip()
            add_to_watchlist(title)
            return f"✅ Добавлено в список: {title}"
        if "ACTION:STATUS:" in answer:
            parts = answer.split("ACTION:STATUS:")[1].split("|")
            title = parts[0].strip()
            status = parts[1].strip() if len(parts) > 1 else "watching"
            update_watchlist_status(title, status)
            return f"✅ {title} → {STATUS_LABELS.get(status, status)}"
        if "ACTION:LIST" in answer:
            wl = get_watchlist()
            watching = [
                w["title"] for w in wl if w.get("status", "watching") == "watching"
            ]
            if not watching:
                return "📺 Список пуст — ничего не смотрю."
            return f"📺 Смотрю сейчас ({len(watching)}):\n" + "\n".join(
                f"• {t}" for t in watching
            )
        if "ACTION:NEWS" in answer:
            recent = get_all_snapshot()[-10:]
            return "🆕 Последние новинки:\n" + "\n".join(
                f"• {a['title']}" for a in recent
            )

        clean = re.sub(r"ACTION:\w+:[^\n]*", "", answer).strip()
        return clean[:4000]


# backward compat — вызывается из main.py
def build_app() -> Application:  # type: ignore[type-arg]
    return AnimeBot().build()


def main() -> None:
    AnimeBot().run()


if __name__ == "__main__":
    main()
