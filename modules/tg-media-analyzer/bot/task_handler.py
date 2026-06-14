"""Task handler — plan → approve → execute pipeline."""

from __future__ import annotations

import logging

import config
from executor import get_executor
from pipeline.task_builder import build_task
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Исполнитель задач через абстракцию. default = SSH-драйвер (CFG.EXECUTOR=ssh);
# переключение на local — отдельным шагом (тогда же адаптируется этот хендлер).
_executor = get_executor()


def approve_keyboard(store_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Одобрить — запустить", callback_data=f"approve:{store_key}"
                ),
                InlineKeyboardButton(
                    "❌ Отменить", callback_data=f"cancel:{store_key}"
                ),
            ]
        ]
    )


def _split(text: str, n: int = 4000) -> list[str]:
    return [text[i : i + n] for i in range(0, len(text), n)]


async def handle_manual_task(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text in tasks topic → get plan → show for approval."""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    # Постановка задачи = RCE через Claude Code → только владелец, только топик задач.
    if not msg.from_user or msg.from_user.id != config.OWNER_USER_ID:
        return
    if msg.message_thread_id != config.TASKS_TOPIC_ID:
        return

    import uuid

    store_key = uuid.uuid4().hex
    title = msg.text[:60] + ("..." if len(msg.text) > 60 else "")
    task_content = build_task(title=title, analysis=msg.text)

    # Сохранить задачу
    context.application.bot_data.setdefault("tasks", {})[store_key] = {
        "title": title,
        "content": task_content,
    }

    # Статус — получаем план
    status = await msg.reply_text("🧠 Составляю план выполнения...")

    try:
        plan = await _executor.get_plan(task_content)
    except Exception as e:
        plan = f"⚠️ Ошибка планирования: {e}"

    await status.delete()

    # Показать план с кнопками одобрения
    header = f"📋 *План: {title}*\n\n"
    chunks = _split(header + plan)
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            # Последний чанк — с кнопками
            await context.bot.send_message(
                chat_id=msg.chat_id,
                message_thread_id=config.TASKS_TOPIC_ID,
                text=chunk,
                parse_mode="Markdown",
                reply_markup=approve_keyboard(store_key),
            )
        else:
            await context.bot.send_message(
                chat_id=msg.chat_id,
                message_thread_id=config.TASKS_TOPIC_ID,
                text=chunk,
                parse_mode="Markdown",
            )


async def handle_task_callback(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ✅ Одобрить / ❌ Отменить."""
    query = update.callback_query
    # Approving runs Claude Code autonomously — same gate as task submission.
    user = query.from_user
    if not user or user.id != config.OWNER_USER_ID:
        await query.answer("Недостаточно прав, сэр.", show_alert=True)
        logger.warning(
            "Неавторизованный user_id=%s нажал кнопку задачи", user.id if user else None
        )
        return
    await query.answer()
    raw = query.data or ""
    if ":" not in raw:
        return

    action, store_key = raw.split(":", 1)
    tasks: dict = context.bot_data.get("tasks", {})
    entry = tasks.get(store_key)

    if action == "cancel":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            message_thread_id=config.TASKS_TOPIC_ID,
            text="❌ Задача отменена.",
        )
        return

    if action == "approve":
        if not entry:
            await query.answer("Задача не найдена.", show_alert=True)
            return

        await query.edit_message_reply_markup(reply_markup=None)

        status = await context.bot.send_message(
            chat_id=query.message.chat_id,
            message_thread_id=config.TASKS_TOPIC_ID,
            text="🤖 Claude Code выполняет задачу автономно...\n⏳ Ожидайте (до 10 минут)",
        )

        try:
            result = await _executor.execute_task(entry["content"])
        except Exception as e:
            result = f"⚠️ Ошибка: {e}"

        await status.delete()

        # Отчёт
        header = f"✅ *Выполнено: {entry['title']}*\n\n"
        chunks = _split(header + f"```\n{result}\n```")
        for chunk in chunks:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                message_thread_id=config.TASKS_TOPIC_ID,
                text=chunk,
                parse_mode="Markdown",
            )

        # Git commit автоматически — сообщение через stdin (git commit -F -),
        # без интерполяции в shell; путь репозитория из env (REPO_DIR ← TASKS_DIR).
        try:
            commit_title = entry["title"][:50].replace("\n", " ")
            await _executor.autocommit(f"feat: {commit_title}")
        except Exception:
            pass
