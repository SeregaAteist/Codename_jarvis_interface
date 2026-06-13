import logging
import os
import re
import sys

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

_JARVIS_ROOT = os.path.expanduser("~/Projects/jarvis")
if _JARVIS_ROOT not in sys.path:
    sys.path.insert(0, _JARVIS_ROOT)

logger = logging.getLogger("bot")

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


def _is_allowed(update: Update) -> bool:
    msg = update.message
    if not msg:
        return False
    user_id = msg.from_user.id if msg.from_user else 0
    if cfg.OWNER_USER_ID and user_id != cfg.OWNER_USER_ID:
        return False
    if msg.chat.type == "private":
        return True
    return (
        str(msg.chat_id) == cfg.GROUP_CHAT_ID
        and msg.message_thread_id == cfg.ANIME_TOPIC_ID
    )


async def _build_answer(text: str) -> str:
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
        clean = f"✅ Добавлено в список: {title}"
    elif "ACTION:STATUS:" in answer:
        parts = answer.split("ACTION:STATUS:")[1].split("|")
        title = parts[0].strip()
        status = parts[1].strip() if len(parts) > 1 else "watching"
        update_watchlist_status(title, status)
        clean = f"✅ {title} → {STATUS_LABELS.get(status, status)}"
    elif "ACTION:LIST" in answer:
        wl = get_watchlist()
        watching = [w["title"] for w in wl if w.get("status", "watching") == "watching"]
        clean = f"📺 Смотрю сейчас ({len(watching)}):\n" + "\n".join(
            f"• {t}" for t in watching
        )
        if not watching:
            clean = "📺 Список пуст — ничего не смотрю."
    elif "ACTION:NEWS" in answer:
        snapshot = get_all_snapshot()
        recent = snapshot[-10:]
        clean = "🆕 Последние новинки:\n" + "\n".join(f"• {a['title']}" for a in recent)
    else:
        clean = answer

    clean = re.sub(r"ACTION:\w+:[^\n]*", "", clean).strip()
    return clean[:4000]


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    if cfg.OWNER_USER_ID and msg.from_user.id != cfg.OWNER_USER_ID:
        return

    thread_id = msg.message_thread_id or 0
    text = (msg.text or "").strip()

    if msg.chat.type == "private":
        pass
    elif cfg.ANIME_TOPIC_ID and thread_id == cfg.ANIME_TOPIC_ID:
        pass
    elif thread_id == INBOX_TOPIC_ID:
        lower = text.lower()
        if lower.startswith(("аниме,", "anime,")):
            text = text[text.index(",") + 1 :].strip()
        else:
            return
    else:
        return

    thinking = await msg.reply_text("🔍 Думаю...")
    try:
        answer = await _build_answer(text)
        await thinking.edit_text(answer)
    except Exception as e:
        logger.error("handle_text error: %s", e)
        await thinking.edit_text(f"❌ Ошибка: {type(e).__name__}: {e}")


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    if cfg.OWNER_USER_ID and msg.from_user.id != cfg.OWNER_USER_ID:
        return

    thread_id = msg.message_thread_id or 0

    if msg.chat.type == "private":
        pass
    elif cfg.ANIME_TOPIC_ID and thread_id == cfg.ANIME_TOPIC_ID:
        pass
    else:
        return

    thinking = await msg.reply_text("🎙 Слушаю...")
    try:
        from modules.bots.voice_handler import transcribe_voice

        text = await transcribe_voice(msg.voice.file_id, ctx.bot.token)
        if not text:
            await thinking.edit_text("❌ Не удалось распознать голосовое сообщение.")
            return
        await thinking.edit_text(f"🎙 Распознано: {text}\n\n🔍 Думаю...")
        answer = await _build_answer(text)
        await thinking.edit_text(answer)
    except Exception as e:
        logger.error("handle_voice error: %s", e)
        await thinking.edit_text(f"❌ Ошибка: {type(e).__name__}: {e}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
        return
    await update.message.reply_text(
        "🎌 Anime бот активен. Пишите вопросы или команды текстом или голосом.\n"
        "/help — список возможностей"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update):
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


def build_app() -> Application:
    app = Application.builder().token(cfg.TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    return app
