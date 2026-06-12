"""Telegram бот Рафаила — одобрение контента, управление уровнями (RF-7).

Запуск: python -m modules.rafail.bot.rafail_bot (из корня JARVIS).
Токен: RAFAIL_BOT_TOKEN (отдельный бот @BotFather). Без него процесс
завершается сразу — fallback на TELEGRAM_BOT_TOKEN дал бы getUpdates
Conflict с com.jarvis.tg-media-analyzer, а меню Рафаила там уже есть.
"""
from __future__ import annotations

import io
import json
import logging
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

from modules.rafail import knowledge_base as kb
from shared.config.secrets import opt

logger = logging.getLogger(__name__)

OWNER_ID = int(opt("OWNER_USER_ID") or 374728252)
PREVIEW_LEN = 500


def _matrix() -> dict[str, list]:
    try:
        return json.loads(kb.get_setting("career_matrix", "{}"))
    except json.JSONDecodeError:
        return {}


def _level_label(track: str) -> str:
    for levels in _matrix().values():
        for key, label, _ in levels:
            if key == track:
                return label
    return track


_DEPT_LABELS = {"sales": "Продажи", "engineers": "Инженеры",
                "installers": "Монтажники", "cross": "Кросс"}


# ── меню ──────────────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    n = len(kb.get_pending(limit=99))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏳ Ожидают одобрения ({n})", callback_data="rb:pend:0")],
        [InlineKeyboardButton("📊 Статистика", callback_data="rb:stats"),
         InlineKeyboardButton("⚙️ Уровень", callback_data="rb:lvl")],
        [InlineKeyboardButton("🔄 Собрать материалы", callback_data="rb:collect"),
         InlineKeyboardButton("⚡ Обработать 10", callback_data="rb:process")],
    ])


def pending_card(idx: int) -> tuple[str, InlineKeyboardMarkup | None]:
    rows = kb.get_pending(limit=99)
    if not rows:
        return "✅ Очередь пуста — нечего одобрять.", None
    idx = max(0, min(idx, len(rows) - 1))
    p = rows[idx]
    dept = kb.get_setting("active_dept", "sales")
    text = (
        f"📚 <b>{p['title']}</b>\n"
        f"Уровень: {_level_label(p.get('track') or '')} | "
        f"Трек: {_DEPT_LABELS.get(dept, dept)}\n"
        f"({idx + 1} из {len(rows)})\n\n"
        f"{(p.get('content') or '')[:PREVIEW_LEN]}…"
    )
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"rb:pend:{idx - 1}"))
    if idx < len(rows) - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"rb:pend:{idx + 1}"))
    keyboard = [
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"rb:ok:{p['id']}:{idx}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"rb:no:{p['id']}"),
         InlineKeyboardButton("👁 Полный текст", callback_data=f"rb:full:{p['id']}")],
        nav + [InlineKeyboardButton("🏠 Меню", callback_data="rb:menu")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def level_menu() -> tuple[str, InlineKeyboardMarkup]:
    dept = kb.get_setting("active_dept", "sales")
    track = kb.get_setting("active_track", "trainee")
    rows = [[InlineKeyboardButton(
        ("✅ " if d == dept else "") + label, callback_data=f"rb:dept:{d}")
        for d, label in _DEPT_LABELS.items() if d in _matrix()]]
    for key, label, _ in _matrix().get(dept, []):
        rows.append([InlineKeyboardButton(
            ("✅ " if key == track else "") + label, callback_data=f"rb:track:{key}")])
    rows.append([InlineKeyboardButton("🏠 Меню", callback_data="rb:menu")])
    text = (f"Текущий: <b>{_level_label(track)}</b> / "
            f"{_DEPT_LABELS.get(dept, dept)}\n\nВыберите отдел и уровень:")
    return text, InlineKeyboardMarkup(rows)


# ── хэндлеры ──────────────────────────────────────────────────────────────────

def _is_owner(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == OWNER_ID)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    await update.message.reply_text("📚 Рафаил на связи.", reply_markup=main_menu())


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    awaiting = ctx.chat_data.pop("rb_await", None)
    if awaiting and awaiting[0] == "reject":
        kb.reject(awaiting[1], update.message.text.strip())
        kb.log_sync("reject", "ok", f"processed={awaiting[1]}")
        await update.message.reply_text("❌ Отклонено, причина записана.",
                                        reply_markup=main_menu())
        return
    await update.message.reply_text("Меню Рафаила:", reply_markup=main_menu())


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    action = parts[1]

    if action == "menu":
        await q.edit_message_text("Меню Рафаила:", reply_markup=main_menu())

    elif action == "pend":
        text, markup = pending_card(int(parts[2]))
        await q.edit_message_text(text, reply_markup=markup or main_menu(),
                                  parse_mode="HTML")

    elif action == "ok":
        pid, idx = int(parts[2]), int(parts[3])
        kb.approve(pid)
        await q.edit_message_text("⏫ Одобрено, заливаю в Moodle…")
        try:
            from modules.rafail.uploader import upload_to_moodle
            res = await upload_to_moodle(pid)
            note = (f"✅ Залито в Moodle: курс {res['course_id']}"
                    + (" (уже был)" if res.get("already") else ""))
        except Exception as e:
            logger.error("[rafail-bot] upload %d: %s", pid, e)
            note = f"⚠️ Одобрено, но загрузка не удалась: {e}"
        text, markup = pending_card(idx)
        await q.edit_message_text(f"{note}\n\n{text}",
                                  reply_markup=markup or main_menu(),
                                  parse_mode="HTML")

    elif action == "no":
        ctx.chat_data["rb_await"] = ("reject", int(parts[2]))
        await q.edit_message_text("📝 Напишите причину отклонения одним сообщением:")

    elif action == "full":
        p = kb.get_processed(int(parts[2]))
        if p:
            buf = io.BytesIO((p.get("content") or "").encode("utf-8"))
            buf.name = f"rafail_{p['id']}.md"
            await q.message.reply_document(buf, caption=p["title"][:200])

    elif action == "lvl":
        text, markup = level_menu()
        await q.edit_message_text(text, reply_markup=markup, parse_mode="HTML")

    elif action == "dept":
        kb.set_setting("active_dept", parts[2])
        levels = _matrix().get(parts[2], [])
        if levels:
            kb.set_setting("active_track", levels[0][0])
        text, markup = level_menu()
        await q.edit_message_text(text, reply_markup=markup, parse_mode="HTML")

    elif action == "track":
        kb.set_setting("active_track", parts[2])
        text, markup = level_menu()
        await q.edit_message_text(text, reply_markup=markup, parse_mode="HTML")

    elif action == "stats":
        s = kb.get_stats()
        await q.edit_message_text(
            "📊 Статистика Рафаила:\n"
            + "\n".join(f"• {k}: {v}" for k, v in s.items()),
            reply_markup=main_menu())

    elif action == "collect":
        await q.edit_message_text("🔄 Собираю материалы…")
        from modules.rafail.collector import collect_all
        summary = await collect_all()
        lines = [f"• {name}: +{n}" for name, n in summary.items() if n] or ["ничего нового"]
        await q.message.reply_text("🔄 Сбор завершён:\n" + "\n".join(lines),
                                   reply_markup=main_menu())

    elif action == "process":
        await q.edit_message_text("⚡ Обрабатываю до 10 материалов…")
        from modules.rafail.processor import process_pending
        res = await process_pending(limit=10)
        await q.message.reply_text(
            f"⚡ Готово: обработано {res.get('processed', 0)}, "
            f"пропущено {res.get('skipped', 0)}, ошибок {res.get('errors', 0)}",
            reply_markup=main_menu())


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = opt("RAFAIL_BOT_TOKEN")
    if not token:
        logger.warning("RAFAIL_BOT_TOKEN не задан — создайте бота у @BotFather "
                       "и добавьте токен в .env. Выход.")
        sys.exit(0)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^rb:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    logger.info("[rafail-bot] запущен (owner=%d)", OWNER_ID)
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
