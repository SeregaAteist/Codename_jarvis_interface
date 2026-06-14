"""Мост Капитан → Telegram: approve_callback на inline-кнопках ✅/❌.

Переиспользует паттерн подтверждения из task_handler. При APPROVE-задаче Supervisor
зовёт approve_callback → публикуем план с кнопками в топик задач и ЖДЁМ нажатие владельца:
  ✅ → Future(True)  → Supervisor исполняет → результат в TG (шина task.completed);
  ❌ → Future(False) → cancelled, уведомление (правка сообщения).
Таймаут ожидания APPROVE_TIMEOUT → безопасная отмена.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import config
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import core.bus as bus
from core.supervisor import register_supervisor

logger = logging.getLogger(__name__)
APPROVE_TIMEOUT = 600  # сек ожидания решения владельца → иначе отмена


class TelegramApprover:
    """Декаплед от telegram: __call__ шлёт план и ждёт Future; resolve(key, bool) её закрывает."""

    def __init__(self, send_func):
        self._send = send_func  # async send_func(plan: str, key: str) -> None
        self._pending: dict[str, asyncio.Future] = {}

    async def __call__(self, plan: str, task: dict) -> bool:
        key = uuid.uuid4().hex[:8]
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[key] = fut
        await self._send(plan, key)
        try:
            return await asyncio.wait_for(fut, timeout=APPROVE_TIMEOUT)
        except asyncio.TimeoutError:
            self._pending.pop(key, None)
            logger.warning("[approver] таймаут подтверждения %s → отмена", key)
            return False

    def resolve(self, key: str, approved: bool) -> bool:
        fut = self._pending.pop(key, None)
        if fut and not fut.done():
            fut.set_result(approved)
            return True
        return False


def setup_supervisor(app):
    """Зарегистрировать Капитана с TG-approve + подписать уведомления о результате."""

    async def _send(plan: str, key: str) -> None:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Выполнить", callback_data=f"sup_ok:{key}"),
                    InlineKeyboardButton("❌ Отмена", callback_data=f"sup_no:{key}"),
                ]
            ]
        )
        await app.bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            message_thread_id=config.TASKS_TOPIC_ID,
            text=f"🧭 *Капитан запрашивает подтверждение:*\n\n{plan}",
            parse_mode="Markdown",
            reply_markup=kb,
        )

    approver = TelegramApprover(_send)
    app.bot_data["supervisor_approver"] = approver
    register_supervisor(approve_callback=approver)

    async def _notify(text: str) -> None:
        try:
            await app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                message_thread_id=config.TASKS_TOPIC_ID,
                text=text,
            )
        except Exception as e:
            logger.error("[supervisor notify] %s", e)

    async def _on_completed(data: dict) -> None:
        await _notify(
            f"✅ Капитан: задача '{data.get('capability')}' выполнена.\n\n"
            f"{str(data.get('result', ''))[:3500]}"
        )

    async def _on_failed(data: dict) -> None:
        await _notify(
            f"⚠️ Капитан: задача '{data.get('capability')}' упала: {data.get('error')}"
        )

    bus.on("task.completed", _on_completed)
    bus.on("task.failed", _on_failed)
    logger.info("[supervisor] зарегистрирован с TG-approve")
    return approver


async def handle_supervisor_callback(update, context) -> None:
    """Кнопки ✅/❌ Капитана (pattern ^sup_(ok|no):). Только владелец."""
    query = update.callback_query
    user = query.from_user
    if not user or user.id != config.OWNER_USER_ID:
        await query.answer("Недостаточно прав, сэр.", show_alert=True)
        logger.warning(
            "Неавторизованный user_id=%s нажал кнопку Капитана",
            user.id if user else None,
        )
        return
    await query.answer()
    raw = query.data or ""
    if ":" not in raw:
        return
    action, key = raw.split(":", 1)
    approved = action == "sup_ok"
    approver: TelegramApprover = context.application.bot_data.get("supervisor_approver")
    ok = bool(approver) and approver.resolve(key, approved)
    base = query.message.text or ""
    if not ok:
        await query.edit_message_text(
            base + "\n\n⚠️ Запрос устарел.", reply_markup=None
        )
        return
    await query.edit_message_text(
        base + ("\n\n✅ Одобрено, выполняю…" if approved else "\n\n❌ Отменено."),
        reply_markup=None,
    )
