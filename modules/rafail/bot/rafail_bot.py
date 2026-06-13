"""Telegram бот Рафаила — одобрение контента, управление уровнями (RF-7).

Запуск: python -m modules.rafail.bot.rafail_bot (из корня JARVIS).
Токен: RAFAIL_BOT_TOKEN (отдельный бот @BotFather). Без него процесс
завершается сразу — fallback на TELEGRAM_BOT_TOKEN дал бы getUpdates
Conflict с com.jarvis.tg-media-analyzer, а меню Рафаила там уже есть.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from modules.rafail import knowledge_base as kb
from modules.rafail.core.profile_manager import get_profile_manager
from modules.rafail.registry.equipment_registry import EquipmentRegistry
from shared.config.secrets import opt

logger = logging.getLogger(__name__)

OWNER_ID = int(opt("OWNER_USER_ID") or 374728252)
RAFAIL_CHAT_ID = int(opt("RAFAIL_CHAT_ID") or 0)
RAFAIL_TOPIC_ID = int(opt("RAFAIL_TOPIC_ID") or 0)
INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID") or 2)
PREVIEW_LEN = 500

_LEARN_KEYWORDS = {"навчання", "курс", "матеріал", "знання", "урок", "обучение", "тема"}

RAFAIL_COMMANDS_PROMPT = """Ты обрабатываешь команды для системы Рафаил.

Определи тип команды и верни ACTION:
- Смена профиля: ACTION:SWITCH_PROFILE:{profile_id}
- Создать профиль: ACTION:CREATE_PROFILE:{name}|{direction}
- Реестр: ACTION:LIST_EQUIPMENT
- Добавить оборудование: ACTION:ADD_EQUIPMENT:{brand}|{model}
- Обычный вопрос: ACTION:QUESTION

Команда: {text}
"""


async def _handle_profile_command(
    text: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Диспетчер профильных команд. Возвращает True если команда обработана."""
    from shared.llm.router import get_router

    router = get_router()
    prompt = RAFAIL_COMMANDS_PROMPT.format(text=text)
    try:
        raw = await router.generate("speed", prompt)
    except Exception as e:
        logger.error("[rafail-bot] profile_command LLM: %s", e)
        return False

    # ищем ACTION: в ответе
    action_line = ""
    for line in raw.splitlines():
        if "ACTION:" in line:
            action_line = line.strip()
            break
    if not action_line:
        return False

    # убираем всё до первого ACTION:
    action_str = action_line[action_line.index("ACTION:") + 7 :]
    parts = action_str.split(":", 1)
    action = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    pm = get_profile_manager()

    if action == "SWITCH_PROFILE":
        profile_id = arg.strip()
        try:
            profile = pm.load(profile_id)
            await update.message.reply_text(f"Профиль переключён: {profile.name}")
        except FileNotFoundError:
            await update.message.reply_text(f"Профиль не найден: {profile_id}")
        return True

    if action == "CREATE_PROFILE":
        name, _, direction = arg.partition("|")
        profile_id = name.strip().lower().replace(" ", "_")
        profile = pm.create(profile_id, name.strip(), direction.strip())
        await update.message.reply_text(f"Профиль создан: {profile.name}")
        return True

    if action == "LIST_EQUIPMENT":
        reg = EquipmentRegistry(pm.active.equipment_dir)
        brands = reg.list_brands()
        if brands:
            await update.message.reply_text(
                "Оборудование:\n" + "\n".join(f"• {b}" for b in brands)
            )
        else:
            await update.message.reply_text("Реестр оборудования пуст.")
        return True

    if action == "ADD_EQUIPMENT":
        await update.message.reply_text("Функция в разработке")
        return True

    # ACTION:QUESTION — продолжить обычную обработку
    return False


def _is_for_rafail(text: str) -> bool:
    return text.lower().startswith(("рафаил,", "rafail,"))


async def _notify_group(bot, text: str) -> None:
    if not RAFAIL_CHAT_ID:
        return
    kwargs: dict = {"chat_id": RAFAIL_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if RAFAIL_TOPIC_ID:
        kwargs["message_thread_id"] = RAFAIL_TOPIC_ID
    try:
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.warning("[rafail-bot] group notify failed: %s", e)


def _reply_thread(update: Update) -> dict:
    """Возвращает message_thread_id если сообщение пришло из топика группы."""
    msg = update.message
    if msg and msg.message_thread_id and update.effective_chat.id == RAFAIL_CHAT_ID:
        return {"message_thread_id": msg.message_thread_id}
    return {}


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


_DEPT_LABELS = {
    "sales": "Продажи",
    "engineers": "Инженеры",
    "installers": "Монтажники",
    "cross": "Кросс",
}


# ── меню ──────────────────────────────────────────────────────────────────────


def main_menu() -> InlineKeyboardMarkup:
    n = len(kb.get_pending(limit=99))
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⏳ Ожидают одобрения ({n})", callback_data="rb:pend:0"
                )
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="rb:stats"),
                InlineKeyboardButton("⚙️ Уровень", callback_data="rb:lvl"),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Собрать материалы", callback_data="rb:collect"
                ),
                InlineKeyboardButton("⚡ Обработать 10", callback_data="rb:process"),
            ],
        ]
    )


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
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"rb:ok:{p['id']}:{idx}"),
            InlineKeyboardButton(
                "❌ Отклонить", callback_data=f"rb:no:{p['id']}:{idx}"
            ),
            InlineKeyboardButton(
                "👁 Полный текст", callback_data=f"rb:full:{p['id']}:{idx}"
            ),
        ],
        nav + [InlineKeyboardButton("🏠 Меню", callback_data="rb:menu")],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def level_menu() -> tuple[str, InlineKeyboardMarkup]:
    dept = kb.get_setting("active_dept", "sales")
    track = kb.get_setting("active_track", "trainee")
    rows = [
        [
            InlineKeyboardButton(
                ("✅ " if d == dept else "") + label, callback_data=f"rb:dept:{d}"
            )
            for d, label in _DEPT_LABELS.items()
            if d in _matrix()
        ]
    ]
    for key, label, _ in _matrix().get(dept, []):
        rows.append(
            [
                InlineKeyboardButton(
                    ("✅ " if key == track else "") + label,
                    callback_data=f"rb:track:{key}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🏠 Меню", callback_data="rb:menu")])
    text = (
        f"Текущий: <b>{_level_label(track)}</b> / "
        f"{_DEPT_LABELS.get(dept, dept)}\n\nВыберите отдел и уровень:"
    )
    return text, InlineKeyboardMarkup(rows)


# ── хэндлеры ──────────────────────────────────────────────────────────────────


def _is_owner(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == OWNER_ID)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    if update.effective_chat.type == "private" and RAFAIL_CHAT_ID:
        await update.message.reply_text(
            f"📚 Рафаил работает в группе.\n"
            f"Управление: перейдите в топик 205 (chat {RAFAIL_CHAT_ID})."
        )
        return
    thread_kwargs = _reply_thread(update)
    await update.effective_chat.send_message(
        "📚 Рафаил на связи.", reply_markup=main_menu(), **thread_kwargs
    )


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    from modules.bots.voice_handler import transcribe_voice

    voice = update.message.voice
    await update.message.reply_text("🎙 Слушаю...")
    text = await transcribe_voice(voice.file_id, ctx.bot.token)
    if not text:
        await update.message.reply_text("❌ Не удалось распознать голосовое сообщение")
        return
    await update.message.reply_text(f"📝 Распознано: {text}")
    update.message.text = text
    await on_text(update, ctx)


async def _approve_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    rows = kb.get_pending(limit=99)
    if not rows:
        await update.message.reply_text("✅ Черга порожня — нічого схвалювати.")
        return
    count = 0
    for p in rows:
        try:
            kb.approve(p["id"])
            count += 1
        except Exception as e:
            logger.error("[rafail] approve_all id=%s: %s", p["id"], e)
    await update.message.reply_text(f"✅ Схвалено: {count} з {len(rows)} матеріалів.")


async def handle_free_question(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    from shared.llm.router import get_router

    router = get_router()
    prompt = (
        "Ти — Рафаіл, куратор бази знань LK Energy Group.\n"
        "Відповідай коротко і по суті українською мовою.\n"
        "Якщо питання про навчальні матеріали — відповідай як експерт з СЕС та продажів.\n\n"
        f"Питання: {text}"
    )
    try:
        answer = await router.generate("quality", prompt)
        await update.message.reply_text(answer[:4000])
    except Exception as e:
        logger.error("[rafail] free_question: %s", e)
        await update.message.reply_text(f"❌ Помилка: {e}")


async def handle_find_manual(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Найти мануал по запросу."""
    from modules.rafail.researchers.web_researcher import WebResearcher
    from shared.llm.router import get_router

    researcher = WebResearcher()
    text = update.message.text or ""
    router = get_router()
    extracted = await router.generate(
        "filter",
        f"Витягни бренд і модель обладнання з тексту. Формат: BRAND|MODEL\nТекст: {text}",
    )

    if "|" in extracted:
        brand, model = extracted.strip().split("|", 1)
        await update.message.reply_text(
            f"Шукаю мануал {brand.strip()} {model.strip()}..."
        )
        pdf_url = await researcher.get_pdf_url(brand.strip(), model.strip())
        if pdf_url:
            await update.message.reply_text(f"Знайдено мануал:\n{pdf_url}")
        else:
            results = await researcher.search_manual(brand.strip(), model.strip())
            if results:
                links = "\n".join(f"• {r.url}" for r in results[:3])
                await update.message.reply_text(f"Результати пошуку:\n{links}")
            else:
                await update.message.reply_text("Мануал не знайдено")
    else:
        await update.message.reply_text(
            "Вкажіть бренд та модель, наприклад: 'знайди мануал Deye SUN-10K'"
        )


async def handle_parse_price(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Парсинг прайс-листа (файл или URL)."""
    from modules.rafail.researchers.price_parser import PriceParser

    parser = PriceParser()
    msg = update.message

    # файл вложенный в следующем сообщении — пока инструкция
    if msg.document:
        import tempfile
        from pathlib import Path

        file = await context.bot.get_file(msg.document.file_id)
        suffix = Path(msg.document.file_name or "price.xlsx").suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            await file.download_to_memory(f)
            tmp = Path(f.name)
        await msg.reply_text("Парсю прайс...")
        items = await parser.parse_excel(tmp)
        tmp.unlink(missing_ok=True)
        cards = parser.to_equipment_cards(items)
        await msg.reply_text(
            f"Знайдено позицій: {len(items)}, розпізнано обладнання: {len(cards)}\n"
            + "\n".join(
                f"• {c.brand} {c.model} — {c.price_current} UAH" for c in cards[:10]
            )
        )
    else:
        await msg.reply_text(
            "Надішліть Excel-файл прайсу як документ, або вкажіть URL: 'прайс https://...'"
        )


async def handle_knowledge_topic(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, text_override: str | None = None
) -> None:
    text = (text_override or update.message.text or "").strip()
    lower = text.lower()

    if await _handle_profile_command(text, update, ctx):
        return

    if any(
        w in lower for w in ("знайди мануал", "найди мануал", "manual", "інструкція")
    ):
        await handle_find_manual(update, ctx)
        return

    if any(w in lower for w in ("прайс", "price", "ціна", "цена")):
        await handle_parse_price(update, ctx)
        return

    if any(w in lower for w in ("pending", "очередь", "ожидают")):
        text_out, markup = pending_card(0)
        await update.message.reply_text(
            text_out, reply_markup=markup or main_menu(), parse_mode="HTML"
        )
        return

    if any(w in lower for w in ("статистика", "stats")):
        s = kb.get_stats()
        await update.message.reply_text(
            "📊 Статистика Рафаила:\n" + "\n".join(f"• {k}: {v}" for k, v in s.items()),
            reply_markup=main_menu(),
        )
        return

    if any(w in lower for w in ("одобри все", "approve all")):
        await _approve_all(update, ctx)
        return

    if any(w in lower for w in ("меню", "menu", "старт")):
        thread_kwargs = _reply_thread(update)
        await update.effective_chat.send_message(
            "Меню Рафаила:", reply_markup=main_menu(), **thread_kwargs
        )
        return

    await handle_free_question(update, ctx, text)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update):
        return
    msg = update.message
    if not msg:
        return
    thread_id = msg.message_thread_id

    if thread_id == RAFAIL_TOPIC_ID and RAFAIL_CHAT_ID:
        await handle_knowledge_topic(update, ctx)
        return

    if thread_id == INBOX_TOPIC_ID and RAFAIL_CHAT_ID:
        text = msg.text or ""
        if not _is_for_rafail(text):
            return
        task_text = text[text.index(",") + 1 :].strip()
        await handle_knowledge_topic(update, ctx, text_override=task_text)
        return

    # другие топики — молчим


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
        await q.edit_message_text(
            text, reply_markup=markup or main_menu(), parse_mode="HTML"
        )

    elif action == "ok":
        pid, idx = int(parts[2]), int(parts[3])
        kb.approve(pid)
        row = kb.get_processed(pid)
        section_title = row["title"] if row else f"ID {pid}"
        await q.edit_message_text("⏫ Одобрено, заливаю в Moodle…")
        track_label = _level_label(row["track"]) if row else ""
        try:
            from modules.rafail.uploader import upload_to_moodle

            res = await upload_to_moodle(pid)
            note = f"✅ Залито в Moodle: курс {res['course_id']}" + (
                " (уже был)" if res.get("already") else ""
            )
            group_note = (
                f"✅ Одобрено и загружено в Moodle\n"
                f"📚 <b>{section_title}</b>\n"
                f"🎓 Уровень: {track_label}"
            )
        except Exception as e:
            logger.error("[rafail-bot] upload %d: %s", pid, e)
            note = f"⚠️ Одобрено, но загрузка не удалась: {e}"
            group_note = (
                f"⚠️ Одобрено, но загрузка не удалась\n"
                f"📚 <b>{section_title}</b>\n"
                f"🎓 Уровень: {track_label}"
            )
        await _notify_group(ctx.bot, group_note)
        text, markup = pending_card(idx)
        await q.edit_message_text(
            f"{note}\n\n{text}", reply_markup=markup or main_menu(), parse_mode="HTML"
        )

    elif action == "no":
        pid, idx = int(parts[2]), int(parts[3])
        kb.reject(pid, "")
        kb.log_sync("reject", "ok", f"processed={pid}")
        text, markup = pending_card(idx)
        await q.edit_message_text(
            f"❌ Відхилено.\n\n{text}",
            reply_markup=markup or main_menu(),
            parse_mode="HTML",
        )

    elif action == "full":
        pid, idx = int(parts[2]), int(parts[3])
        p = kb.get_processed(pid)
        if p:
            content = (p.get("content") or "")[:3500]
            back_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Назад", callback_data=f"rb:pend:{idx}")]]
            )
            await q.edit_message_text(
                f"<b>{p['title']}</b>\n\n{content}",
                reply_markup=back_markup,
                parse_mode="HTML",
            )

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
            "📊 Статистика Рафаила:\n" + "\n".join(f"• {k}: {v}" for k, v in s.items()),
            reply_markup=main_menu(),
        )

    elif action == "collect":
        await q.edit_message_text("🔄 Собираю материалы…")
        from modules.rafail.collector import collect_all

        summary = await collect_all()
        lines = [f"• {name}: +{n}" for name, n in summary.items() if n] or [
            "ничего нового"
        ]
        await q.message.reply_text(
            "🔄 Сбор завершён:\n" + "\n".join(lines), reply_markup=main_menu()
        )

    elif action == "process":
        await q.edit_message_text("⚡ Обрабатываю до 10 материалов…")
        from modules.rafail.processor import process_pending

        res = await process_pending(limit=10)
        await q.message.reply_text(
            f"⚡ Готово: обработано {res.get('processed', 0)}, "
            f"пропущено {res.get('skipped', 0)}, ошибок {res.get('errors', 0)}",
            reply_markup=main_menu(),
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    token = opt("RAFAIL_BOT_TOKEN")
    if not token:
        logger.warning(
            "RAFAIL_BOT_TOKEN не задан — создайте бота у @BotFather "
            "и добавьте токен в .env. Выход."
        )
        sys.exit(0)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^rb:"))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    logger.info("[rafail-bot] запущен (owner=%d)", OWNER_ID)
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
