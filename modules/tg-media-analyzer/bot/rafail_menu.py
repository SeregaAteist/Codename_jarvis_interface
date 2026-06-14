"""Рафаил — кнопочный интерфейс (RF-12). Никаких slash-команд, всё на русском.

Меню открывается словом «рафаил». Callback-префиксы:
  rf:    — навигация и действия меню
  rfap:  — одобрение материалов (✅ Залить / 📝 Правки / ❌ Отклонить / 👁 Просмотр)

Текстовые состояния (поиск, добавление источника, правки) — через
chat_data["rafail_await"], роутер текста подключён в main.py.
"""

from __future__ import annotations

import asyncio
import logging

import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_agent = None  # RafailAgent — создаётся в setup_rafail
_approver = None  # RafailApprover


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Статус", callback_data="rf:status"),
                InlineKeyboardButton("📥 Собрать сейчас", callback_data="rf:collect"),
            ],
            [
                InlineKeyboardButton("🔧 Модули", callback_data="rf:modules"),
                InlineKeyboardButton("📝 Тесты", callback_data="rf:quizzes"),
            ],
            [
                InlineKeyboardButton("⏳ Ожидают", callback_data="rf:pending"),
                InlineKeyboardButton("👥 Прогресс", callback_data="rf:progress"),
            ],
            [
                InlineKeyboardButton("🔍 Поиск", callback_data="rf:search"),
                InlineKeyboardButton("🔄 Синхр. CRM", callback_data="rf:crm"),
            ],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="rf:settings")],
        ]
    )


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📡 Источники", callback_data="rf:src_list"),
                InlineKeyboardButton("💬 Промпты", callback_data="rf:prompt_list"),
            ],
            [
                InlineKeyboardButton("📁 Папки Drive", callback_data="rf:folder_list"),
                InlineKeyboardButton("← Назад", callback_data="rf:menu"),
            ],
        ]
    )


def approval_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Залить", callback_data=f"rfap:ok:{key}"),
                InlineKeyboardButton("📝 Правки", callback_data=f"rfap:edit:{key}"),
            ],
            [
                InlineKeyboardButton("❌ Отклонить", callback_data=f"rfap:no:{key}"),
                InlineKeyboardButton("👁 Просмотр", callback_data=f"rfap:view:{key}"),
            ],
        ]
    )


async def open_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or (config.TELEGRAM_CHAT_ID and msg.chat_id != config.TELEGRAM_CHAT_ID):
        return
    await msg.reply_text("🧠 Рафаил — База знаний LK Energy", reply_markup=main_menu())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = (query.data or "").split(":", 1)[1]
    chat_id = query.message.chat_id
    thread = query.message.message_thread_id

    async def reply(text: str, kb: InlineKeyboardMarkup | None = None):
        await context.bot.send_message(
            chat_id=chat_id, message_thread_id=thread, text=text[:4000], reply_markup=kb
        )

    from modules.rafail import knowledge_base as kb_db

    if action == "menu":
        await reply("🧠 Рафаил — База знаний LK Energy", main_menu())

    elif action == "status":
        s = kb_db.get_stats()
        await reply(
            "📊 Статус базы знаний:\n"
            f"• Материалов: {s['materials']}\n"
            f"• На одобрении: {s['pending']}\n"
            f"• Одобрено: {s['approved']}\n"
            f"• Отклонено: {s['rejected']}\n"
            f"• Залито: {s['uploaded']} (Moodle-записей: {s['moodle_entries']})",
            main_menu(),
        )

    elif action == "collect":
        await reply("⏳ Собираю материалы по всем источникам...")
        try:
            summary = await _agent.daily_collect()
            await reply(_agent._fmt_collect(summary), main_menu())
        except Exception as e:  # noqa: BLE001
            await reply(f"⚠️ Ошибка сбора: {e}", main_menu())

    elif action == "modules":
        await reply(
            "🔧 Запускаю слияние правок ++ (М1-М5).\n"
            "Планы на одобрение придут отдельными сообщениями."
        )
        asyncio.create_task(_run_fix_modules(context, chat_id, thread))

    elif action == "quizzes":
        await reply(
            "📝 Генерация тестов требует контента модулей из Drive.\n"
            "Запускаю по модулям М1-М5..."
        )
        asyncio.create_task(_run_quizzes(context, chat_id, thread))

    elif action == "pending":
        rows = kb_db.get_pending()
        if not rows:
            await reply("⏳ Материалов на одобрении нет.", main_menu())
        else:
            lines = ["⏳ На одобрении:"]
            for r in rows[:15]:
                lines.append(f"• #{r['id']} [{r['content_type']}] {r['title']}")
            await reply("\n".join(lines), main_menu())

    elif action == "progress":
        await reply("⏳ Собираю данные из Moodle...")
        try:
            await reply(await _agent.generate_progress_report(), main_menu())
        except Exception as e:  # noqa: BLE001
            await reply(f"⚠️ Moodle недоступен: {e}", main_menu())

    elif action == "search":
        context.chat_data["rafail_await"] = "search"
        await reply("🔍 Напишите поисковый запрос:")

    elif action == "crm":
        try:
            await reply(await _agent.sync_from_crm(), main_menu())
        except Exception as e:  # noqa: BLE001
            await reply(f"⚠️ CRM: {e}", main_menu())

    elif action == "settings":
        await reply("⚙️ Настройки", settings_menu())

    # ── источники ─────────────────────────────────────────────────────────────
    elif action == "src_list":
        rows = kb_db.get_sources(enabled_only=False)
        lines = ["📡 Источники:"]
        buttons = []
        for r in rows:
            mark = "🟢" if r["enabled"] else "⚪"
            lines.append(f"{mark} #{r['id']} [{r['domain']}/{r['track']}] {r['name']}")
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"🗑 {r['name'][:30]}", callback_data=f"rf:src_del_{r['id']}"
                    )
                ]
            )
        buttons.append(
            [
                InlineKeyboardButton("+ Добавить", callback_data="rf:src_add"),
                InlineKeyboardButton("← Назад", callback_data="rf:settings"),
            ]
        )
        await reply("\n".join(lines), InlineKeyboardMarkup(buttons))

    elif action == "src_add":
        context.chat_data["rafail_await"] = "src_add"
        await reply(
            "📡 Формат: домен название url [rss|web] [трек]\n"
            "Пример: ses Ecotown https://ecotown.com.ua/feed/ rss all"
        )

    elif action.startswith("src_del_"):
        kb_db.delete_source(int(action.rsplit("_", 1)[1]))
        await reply("🗑 Источник удалён.", settings_menu())

    # ── промпты ───────────────────────────────────────────────────────────────
    elif action == "prompt_list":
        names = kb_db.list_prompts()
        buttons = [
            [InlineKeyboardButton(f"👁 {n}", callback_data=f"rf:prompt_show_{n}")]
            for n in names
        ]
        buttons.append([InlineKeyboardButton("← Назад", callback_data="rf:settings")])
        await reply(
            "💬 Промпты (контент курсов — украинский, это норма):",
            InlineKeyboardMarkup(buttons),
        )

    elif action.startswith("prompt_show_"):
        name = action.removeprefix("prompt_show_")
        try:
            await reply(f"💬 {name}:\n\n{kb_db.get_prompt(name)}", settings_menu())
        except KeyError:
            await reply("⚠️ Промпт не найден.", settings_menu())

    # ── Drive-папки ───────────────────────────────────────────────────────────
    elif action == "folder_list":
        rows = kb_db.get_folders_full()
        lines = ["📁 Папки Drive:"]
        buttons = []
        for r in rows:
            lines.append(f"• {r['key']}: {r['title'] or r['folder_id'][:20]}")
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"🗑 {r['key']}", callback_data=f"rf:folder_del_{r['key']}"
                    )
                ]
            )
        buttons.append(
            [
                InlineKeyboardButton("+ Добавить", callback_data="rf:folder_add"),
                InlineKeyboardButton("← Назад", callback_data="rf:settings"),
            ]
        )
        await reply("\n".join(lines), InlineKeyboardMarkup(buttons))

    elif action == "folder_add":
        context.chat_data["rafail_await"] = "folder_add"
        await reply(
            "📁 Формат: ключ folder_id [название]\n"
            "Пример: section_new 1AbCdEf... Новый раздел"
        )

    elif action.startswith("folder_del_"):
        kb_db.delete_folder(action.removeprefix("folder_del_"))
        await reply("🗑 Папка удалена.", settings_menu())


async def handle_approval_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """rfap: — решения владельца по материалам."""
    query = update.callback_query
    await query.answer()
    _, decision, key = (query.data or "").split(":", 2)
    from modules.rafail import knowledge_base as kb_db

    if decision == "ok":
        if _approver.resolve(key, "approve"):
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("✅ Одобрено — заливаю.")
        else:
            await query.message.reply_text("⚠️ Запрос устарел.")

    elif decision == "no":
        if _approver.resolve(key, "reject:отклонено владельцем"):
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("❌ Отклонено.")
        else:
            await query.message.reply_text("⚠️ Запрос устарел.")

    elif decision == "edit":
        context.chat_data["rafail_await"] = f"edit:{key}"
        await query.message.reply_text(
            "📝 Пришлите правки текстом — применю и покажу новую версию."
        )

    elif decision == "view":
        pid = _approver.get_processed_id(key)
        row = kb_db.get_processed(pid) if pid else None
        if not row:
            await query.message.reply_text("⚠️ Материал не найден.")
            return
        content = row["content"] or ""
        for i in range(0, min(len(content), 12000), 4000):
            await query.message.reply_text(content[i : i + 4000])


async def handle_text_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Тексты для состояний Рафаила. True — если обработано."""
    state = context.chat_data.get("rafail_await")
    if not state:
        return False
    context.chat_data.pop("rafail_await", None)
    text = (update.effective_message.text or "").strip()
    msg = update.effective_message
    from modules.rafail import knowledge_base as kb_db

    if state == "search":
        await msg.reply_text("🔍 Ищу...")
        await msg.reply_text(
            (await _agent.answer_knowledge_query(text))[:4000], reply_markup=main_menu()
        )
        return True

    if state == "src_add":
        parts = text.split()
        if len(parts) < 3:
            await msg.reply_text(
                "⚠️ Нужно минимум: домен название url", reply_markup=settings_menu()
            )
            return True
        domain, name, url = parts[0], parts[1], parts[2]
        type_ = parts[3] if len(parts) > 3 else "rss"
        track = parts[4] if len(parts) > 4 else "all"
        try:
            kb_db.add_source(domain, name, url, type_, track=track)
            await msg.reply_text(
                f"✅ Источник «{name}» добавлен.", reply_markup=settings_menu()
            )
        except Exception as e:  # noqa: BLE001
            await msg.reply_text(f"⚠️ {e}", reply_markup=settings_menu())
        return True

    if state == "folder_add":
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            await msg.reply_text(
                "⚠️ Нужно: ключ folder_id [название]", reply_markup=settings_menu()
            )
            return True
        kb_db.add_folder(parts[0], parts[1], parts[2] if len(parts) > 2 else "")
        await msg.reply_text(
            f"✅ Папка «{parts[0]}» добавлена.", reply_markup=settings_menu()
        )
        return True

    if state.startswith("edit:"):
        key = state.split(":", 1)[1]
        await msg.reply_text("📝 Применяю правки...")
        try:
            asyncio.create_task(_approver.revise(key, text))
            await msg.reply_text(
                "📝 Правки приняты — новая версия придёт на одобрение."
            )
        except Exception as e:  # noqa: BLE001
            await msg.reply_text(f"⚠️ {e}")
        return True

    return True


# ── фоновые операции ──────────────────────────────────────────────────────────


async def _run_fix_modules(context, chat_id: int, thread) -> None:
    try:
        results = await _agent.fix_pending_modules()
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread,
            text=_agent._fmt_fix(results),
            reply_markup=main_menu(),
        )
    except Exception as e:  # noqa: BLE001
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread,
            text=f"⚠️ Слияние правок: {e}",
            reply_markup=main_menu(),
        )


async def _run_quizzes(context, chat_id: int, thread) -> None:
    try:
        from modules.rafail.connectors.drive import DriveConnector
        from modules.rafail.fixer import PENDING_MODULES, match_module_files

        drive = _agent.drive or DriveConnector()
        files = await drive.list_folder(drive.folder("course_ses"))
        contents: dict[str, str] = {}
        for module in PENDING_MODULES:
            mfile, _ = match_module_files(files, module)
            if mfile:
                contents[module] = await drive.read_file(mfile["id"])
        if not contents:
            raise RuntimeError("файлы модулей в Drive не найдены")
        results = await _agent.generate_quizzes(contents)
        lines = ["📝 Тесты:"]
        for r in results:
            lines.append(f"• {r['module']}: {r['status']}")
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread,
            text="\n".join(lines),
            reply_markup=main_menu(),
        )
    except Exception as e:  # noqa: BLE001
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread,
            text=f"⚠️ Тесты: {e}",
            reply_markup=main_menu(),
        )


# ── инициализация ─────────────────────────────────────────────────────────────


def setup_rafail(app) -> None:
    """Создать агента с TG-approver и зарегистрировать в реестре."""
    global _agent, _approver
    import core.registry as registry
    from agents.rafail import RafailAgent
    from modules.rafail import db as rafail_db
    from modules.rafail.approver import RafailApprover

    rafail_db.init_db()

    async def send_plan(message: str, key: str, processed_id: int) -> None:
        await app.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            message_thread_id=config.TASKS_TOPIC_ID or None,
            text=message,
            reply_markup=approval_keyboard(key),
        )

    _approver = RafailApprover(send_plan)
    _agent = RafailAgent(approver=_approver)
    registry.register(_agent)
    logger.info("[rafail] агент зарегистрирован, меню активно")
