import asyncio
import logging

from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from agents.db_agent import (
    get_watchlist, get_recent_episodes, add_to_watchlist,
    update_status_by_id, get_all_snapshot, WATCHLIST_STATUSES
)
from agents.recommend_agent import get_recommendations
from config import cfg

logger = logging.getLogger("bot")

WAITING_ADD_QUERY = 1

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔍 Скан",      "🆕 Результаты",  "🤖 Рекомендации"],
        ["📋 Вотчлист",  "➕ Добавить",    "➖ Убрать"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

MENU_BUTTONS = {"🔍 Скан", "🆕 Результаты", "🤖 Рекомендации",
                "📋 Вотчлист", "➕ Добавить", "➖ Убрать"}

STATUS_LABELS = {
    "watching":  "▶️ Смотрю",
    "completed": "✅ Просмотрено",
    "dropped":   "❌ Дропнул",
    "planned":   "📅 Запланировано",
}


def status_filter_keyboard() -> InlineKeyboardMarkup:
    """Фильтр вотчлиста по статусу (A-8)."""
    row1 = [
        InlineKeyboardButton(STATUS_LABELS["watching"],  callback_data="wlfilter:watching"),
        InlineKeyboardButton(STATUS_LABELS["completed"], callback_data="wlfilter:completed"),
    ]
    row2 = [
        InlineKeyboardButton(STATUS_LABELS["dropped"],   callback_data="wlfilter:dropped"),
        InlineKeyboardButton(STATUS_LABELS["planned"],   callback_data="wlfilter:planned"),
    ]
    return InlineKeyboardMarkup([row1, row2])


def status_change_keyboard(item_id: int, current: str, url: str) -> InlineKeyboardMarkup:
    """Кнопки смены статуса под тайтлом: все статусы кроме текущего (A-8)."""
    safe_url = url if url and url.startswith("http") else cfg.BASE_URL
    buttons = [
        InlineKeyboardButton(label, callback_data=f"status:{item_id}:{status}")
        for status, label in STATUS_LABELS.items()
        if status != current
    ]
    return InlineKeyboardMarkup([
        buttons[:2],
        buttons[2:],
        [InlineKeyboardButton("🔗 Смотреть на сайте", url=safe_url)],
    ])


def fuzzy_search(query: str, catalog: list, limit: int = 8) -> list:
    q = query.lower().strip()
    scored = []
    for item in catalog:
        title = item.get("title", "").lower()
        if q in title:
            score = 100 - len(title)
        else:
            words = [w for w in q.split() if len(w) > 1]
            hits  = sum(1 for w in words if w in title)
            if hits == 0:
                continue
            score = hits * 20 - len(title)
        scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:limit]]


def is_allowed(update) -> bool:
    if not update.message:
        return True
    chat_id  = str(update.message.chat_id)
    thread   = update.message.message_thread_id
    user_id  = update.message.from_user.id if update.message.from_user else 0
    priv     = (update.message.chat.type == "private"
                and (not cfg.OWNER_USER_ID or user_id == cfg.OWNER_USER_ID))
    group_ok = (chat_id == cfg.GROUP_CHAT_ID and thread == cfg.THREAD_ID)
    return priv or group_ok


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ <b>J.A.R.V.I.S. Anime Monitor</b> онлайн, сэр.\n\n"
        f"Автосканирование: {', '.join(f'{h}:05' for h in cfg.SCAN_HOURS)}\n"
        "Управление — кнопками ниже.",
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD,
    )


async def _send_watchlist_items(send, status: str):
    """Вывести тайтлы вотчлиста выбранного статуса с кнопками смены."""
    items = get_watchlist(status=status)
    if not items:
        await send(f"Раздел «{STATUS_LABELS[status]}» пуст.")
        return

    snapshot_list = get_all_snapshot()
    snapshot = {}
    for a in snapshot_list:
        snapshot[a["title"].lower()] = a
        if a.get("url"):
            snapshot[a["url"]] = a

    for item in items:
        meta = (
            snapshot.get(item["url"]) or
            snapshot.get(item["title"].lower()) or
            {}
        )
        ep    = meta.get("episode", "")
        score = f"  ·  MAL {meta['mal_score']}" if meta.get("mal_score") else ""
        url   = meta.get("url") or item.get("url") or cfg.BASE_URL

        caption = f"<b>{item['title']}</b>\n{STATUS_LABELS[item['status']]}"
        if ep:
            caption += f"\nПоследняя серия: {ep}"
        if score:
            caption += score

        await send(
            caption,
            parse_mode="HTML",
            reply_markup=status_change_keyboard(item["id"], item["status"], url),
        )
        await asyncio.sleep(0.3)


async def handle_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    watchlist = get_watchlist()
    if not watchlist:
        await update.message.reply_text(
            "📋 Вотчлист пуст.\nНажмите «➕ Добавить» чтобы добавить аниме.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    counts = {s: 0 for s in WATCHLIST_STATUSES}
    for w in watchlist:
        counts[w.get("status", "watching")] = counts.get(w.get("status", "watching"), 0) + 1
    summary = "  ·  ".join(
        f"{STATUS_LABELS[s]}: {n}" for s, n in counts.items() if n
    )

    await update.message.reply_text(
        f"📋 <b>Вотчлист ({len(watchlist)})</b>\n{summary}\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=status_filter_keyboard(),
    )


async def handle_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    episodes = get_recent_episodes(limit=15)
    if not episodes:
        await update.message.reply_text(
            "🆕 Новых серий нет.\nЗапустите 🔍 Скан.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    lines = ["🆕 <b>Последние обновления:</b>\n"]
    for ep in episodes:
        ep_str = f" [{ep['episode']}]" if ep.get("episode") else ""
        url    = ep.get("anime_url", cfg.BASE_URL)
        lines.append(
            f"• <a href='{url}'>{ep['anime_title']}</a>{ep_str}\n"
            f"  <i>{ep['detected_at'][:16]}</i>"
        )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD,
        disable_web_page_preview=False,
    )


async def handle_recommend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    watchlist = get_watchlist(status="watching")
    if not watchlist:
        await update.message.reply_text(
            "📋 Вотчлист пуст — добавьте аниме чтобы получить рекомендации.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    msg    = await update.message.reply_text("🤖 Анализирую вотчлист... (10–30 сек)")
    result = await get_recommendations()
    await msg.edit_text(
        f"🤖 <b>Рекомендации J.A.R.V.I.S.:</b>\n\n{result}",
        parse_mode="HTML",
    )


async def handle_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    from main import run_scan
    await update.message.reply_text("🔍 Запускаю сканирование...", reply_markup=MAIN_KEYBOARD)
    new_count = await run_scan()
    await update.message.reply_text(
        f"✅ Сканирование завершено.\nНовых обновлений: {new_count}",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    catalog = get_all_snapshot()
    await update.message.reply_text(
        f"🔎 Введите название или часть названия аниме:\n"
        f"<i>(каталог: {len(catalog)} тайтлов)</i>",
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD,
    )
    return WAITING_ADD_QUERY


async def handle_add_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.message.text.strip()

    if query in MENU_BUTTONS:
        await update.message.reply_text("Отменено.", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    catalog = get_all_snapshot()
    results = fuzzy_search(query, catalog, limit=8)

    if not results:
        await update.message.reply_text(
            f"❌ По запросу «{query}» ничего не найдено.\n\n"
            f"Каталог содержит {len(catalog)} тайтлов.\n"
            f"Попробуйте другое слово или запустите 🔍 Скан.",
            reply_markup=MAIN_KEYBOARD,
        )
        return ConversationHandler.END

    ctx.user_data["add_results"] = results

    buttons = []
    for i, r in enumerate(results):
        score_str = f" · MAL {r['mal_score']}" if r.get("mal_score") else ""
        label = f"{r['title'][:50]}{score_str}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"addconfirm:{i}")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="addcancel")])

    await update.message.reply_text(
        f"🔎 По запросу «{query}» найдено {len(results)}:\n"
        f"Выберите нужный тайтл:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return ConversationHandler.END


async def handle_drop_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    watchlist = get_watchlist(status="watching")
    if not watchlist:
        await update.message.reply_text("Вотчлист пуст.", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"❌ {w['title'][:55]}", callback_data=f"status:{w['id']}:dropped")]
        for w in watchlist
    ])
    await update.message.reply_text("➖ Выберите что убрать из вотчлиста:", reply_markup=keyboard)
    return ConversationHandler.END


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split(":")
    action = parts[0]

    if action == "addconfirm" and len(parts) >= 2:
        results = ctx.user_data.get("add_results", [])
        try:
            item = results[int(parts[1])]
        except (IndexError, ValueError):
            await query.edit_message_text("⚠️ Сессия устарела, повторите поиск.")
            return
        title = item["title"]
        url   = item.get("url", "")
        added = add_to_watchlist(title, url)
        text  = (
            f"✅ <b>{title}</b> добавлен в отслеживаемое.\nУведомлю когда выйдет новая серия, сэр. 🔔"
            if added else
            f"⚠️ <b>{title}</b> уже в вотчлисте — вернул в «Смотрю»."
        )
        await query.edit_message_text(text, parse_mode="HTML")

    elif action == "addcancel":
        await query.edit_message_text("Отменено.")

    elif action == "wlfilter" and len(parts) >= 2 and parts[1] in WATCHLIST_STATUSES:
        status = parts[1]
        await query.edit_message_text(
            f"📋 Раздел: <b>{STATUS_LABELS[status]}</b>", parse_mode="HTML"
        )
        await _send_watchlist_items(query.message.reply_text, status)

    elif action == "status" and len(parts) >= 3 and parts[2] in WATCHLIST_STATUSES:
        try:
            item_id = int(parts[1])
        except ValueError:
            await query.edit_message_text("⚠️ Некорректный запрос.")
            return
        new_status = parts[2]
        if update_status_by_id(item_id, new_status):
            await query.edit_message_text(
                f"Статус обновлён: <b>{STATUS_LABELS[new_status]}</b>",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text("⚠️ Запись не найдена — обновите вотчлист.")


async def handle_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Используйте кнопки меню, сэр.",
        reply_markup=MAIN_KEYBOARD,
    )


def build_app() -> Application:
    app = Application.builder().token(cfg.TELEGRAM_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить$"), handle_add_start)],
        states={WAITING_ADD_QUERY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_query)
        ]},
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(add_conv)
    app.add_handler(MessageHandler(filters.Regex("^📋 Вотчлист$"),     handle_watchlist))
    app.add_handler(MessageHandler(filters.Regex("^🆕 Результаты$"),   handle_new))
    app.add_handler(MessageHandler(filters.Regex("^🤖 Рекомендации$"), handle_recommend))
    app.add_handler(MessageHandler(filters.Regex("^🔍 Скан$"),         handle_scan))
    app.add_handler(MessageHandler(filters.Regex("^➖ Убрать$"),       handle_drop_start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT, handle_unknown))

    return app
