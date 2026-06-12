"""Аниме — кнопочный интерфейс (A-8). Никаких slash-команд.

Меню открывается словом «аниме» в чате владельца. Все callback-и с
префиксом an:. Ввод текста (поиск/добавление) — через состояние
chat_data["anime_await"], текст-роутер подключается в main.py ПЕРЕД
обработчиком задач.
"""
from __future__ import annotations

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)

ANIME_TOPIC_ID = int(os.getenv("ANIME_TOPIC_ID", "0") or 0)

_STATUS_RU = {
    "watching": "▶️ Смотрю", "completed": "✅ Просмотрено", "planned": "📅 В планах",
    "dropped": "🗑 Брошено", "on_hold": "⏸ Отложено",
}


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Список", callback_data="an:list"),
         InlineKeyboardButton("🔍 Поиск", callback_data="an:search")],
        [InlineKeyboardButton("➕ Добавить", callback_data="an:add"),
         InlineKeyboardButton("🎯 Рекомендации", callback_data="an:rec")],
        [InlineKeyboardButton("🔄 Синхр. Shikimori", callback_data="an:sync")],
    ])


def _watch_kb(url: str | None) -> InlineKeyboardMarkup | None:
    if not url:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Смотреть", url=url)]])


async def notify_episode(app, text: str, url: str | None) -> None:
    """notify_func для AnimeAgent — уведомление о новой серии."""
    await app.bot.send_message(
        chat_id=config.TELEGRAM_CHAT_ID,
        message_thread_id=ANIME_TOPIC_ID or None,
        text=text,
        reply_markup=_watch_kb(url),
    )


async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Слово «аниме» → главное меню."""
    msg = update.effective_message
    if not msg or (config.TELEGRAM_CHAT_ID and msg.chat_id != config.TELEGRAM_CHAT_ID):
        return
    await msg.reply_text("🎌 Аниме", reply_markup=main_menu())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = (query.data or "").split(":", 1)[1] if ":" in (query.data or "") else ""
    chat_id = query.message.chat_id
    thread = query.message.message_thread_id

    async def reply(text: str, kb: InlineKeyboardMarkup | None = None):
        await context.bot.send_message(chat_id=chat_id, message_thread_id=thread,
                                       text=text[:4000], reply_markup=kb)

    if action == "list":
        from modules.anime import watchlist as wl
        rows = wl.get_all()
        if not rows:
            await reply("📋 Вотч-лист пуст. Нажмите ➕ Добавить.", main_menu())
            return
        lines = ["📋 Ваш вотч-лист:"]
        for r in rows[:30]:
            score = f" ⭐{r['score']}" if r.get("score") else ""
            lines.append(f"• {r.get('title_ru') or '?'} — "
                         f"{_STATUS_RU.get(r['status'], r['status'])}{score}")
        await reply("\n".join(lines), main_menu())

    elif action in ("search", "add"):
        context.chat_data["anime_await"] = action
        await reply("Напишите название тайтла:")

    elif action == "rec":
        from agents.anime import AnimeAgent
        await reply(await AnimeAgent().get_recommendations(), main_menu())

    elif action == "sync":
        from agents.anime import AnimeAgent
        await reply(await AnimeAgent().sync_shikimori(), main_menu())

    elif action.startswith("wl_add_"):
        # добавить найденный тайтл в watchlist
        from modules.anime import watchlist as wl
        title_id = int(action.rsplit("_", 1)[1])
        wl.add(title_id, status="planned")
        await reply("✅ Добавлено в планы. Статус меняется в 📋 Списке.", main_menu())

    elif action.startswith("wl_st_"):
        # цикл статуса записи: planned → watching → completed → planned
        from modules.anime import watchlist as wl
        wid = int(action.rsplit("_", 1)[1])
        row = wl.get(wid)
        if row:
            nxt = {"planned": "watching", "watching": "completed"}.get(row["status"], "planned")
            wl.update_status(wid, nxt)
            await reply(f"Статус: {_STATUS_RU[nxt]}", main_menu())


async def handle_text_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Текстовый ввод после 🔍/➕. Возвращает True, если текст обработан."""
    state = context.chat_data.pop("anime_await", None)
    if not state:
        return False
    query = (update.effective_message.text or "").strip()
    if not query:
        return True

    from modules.anime import db
    with db.connect() as c:
        rows = c.execute(
            "SELECT id, title_ru, title_en, year, rating_animevost FROM titles "
            "WHERE title_ru LIKE ? OR title_en LIKE ? ORDER BY rating_animevost DESC LIMIT 8",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()

    if not rows:
        await update.effective_message.reply_text(
            f"🔍 «{query}» в каталоге не найдено. Каталог пополняется импортом Animevost.",
            reply_markup=main_menu())
        return True

    buttons = [[InlineKeyboardButton(
        f"➕ {r['title_ru'][:40]} ({r['year'] or '?'})",
        callback_data=f"an:wl_add_{r['id']}")] for r in rows]
    await update.effective_message.reply_text(
        f"🔍 Найдено по «{query}» — нажмите чтобы добавить:",
        reply_markup=InlineKeyboardMarkup(buttons))
    return True
