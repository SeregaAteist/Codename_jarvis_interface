"""Approver — паттерн Капитана для контента Рафаила (RF-8).

Рафаил готовит материал → шлёт план владельцу → ждёт решения:
  ✅ Залити    → approved → upload-пайплайн (Drive/Moodle)
  📝 Правки    → владелец пишет правки текстом → apply → повторный запрос
  ❌ Відхилити → rejected (+причина)
  👁 Переглянути → полный текст материала в чат

Декаплед от Telegram: send_func инжектируется (бот подключит в RF-12).
Решения закрывают Future через resolve(); таймаут 24 ч → отмена.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Awaitable, Callable

from modules.rafail import knowledge_base as kb

logger = logging.getLogger(__name__)

OWNER_ID = 374728252
APPROVE_TIMEOUT = 24 * 3600  # 24 часа по ТЗ

# send_func(message: str, key: str, processed_id: int) — публикация плана с кнопками
SendFunc = Callable[[str, str, int], Awaitable[None]]

_DOMAIN_ICONS = {"ses": "☀️", "energy": "⚡", "sales": "💼", "internal": "🏢"}


def format_approval_message(processed: dict, sources_count: int = 1) -> str:
    """Сообщение владельцу по шаблону ТЗ."""
    content = processed.get("content") or ""
    sections = max(1, content.count("\n## ") + content.count("\n**"))
    questions = content.count('"question"')
    summary = " ".join(content.replace("#", "").split()[:40])

    # domain живёт в materials — достаём через material_id
    domain = "internal"
    if processed.get("material_id"):
        mat = kb.get_material(processed["material_id"])
        if mat:
            domain = mat.get("domain") or "internal"
    lines = [
        "📚 Рафаїл підготував матеріал",
        "",
        f"📂 Домен: {_DOMAIN_ICONS.get(domain, '')} {domain}",
        f"👥 Трек: {processed.get('track', 'all')}",
        f"📋 Тип: {processed.get('content_type', '?')}",
        f"📌 Тема: {processed.get('title', '?')}",
        "",
        "📊 Склад:",
        f"• Джерел: {sources_count}",
        f"• Секцій: {sections}",
    ]
    if questions:
        lines.append(f"• Питань тесту: {questions}")
    lines += ["", f"💡 {summary}..."]
    return "\n".join(lines)


class RafailApprover:
    """Очередь одобрений: submit() шлёт план и ждёт; resolve()/revise() закрывают."""

    def __init__(self, send_func: SendFunc):
        self._send = send_func
        self._pending: dict[str, asyncio.Future] = {}
        self._processed_ids: dict[str, int] = {}

    async def submit(self, processed_id: int, sources_count: int = 1,
                     timeout: float = APPROVE_TIMEOUT) -> str:
        """Отправить материал на одобрение. Возвращает финальный статус:
        approved / rejected / timeout."""
        processed = kb.get_processed(processed_id)
        if not processed:
            raise ValueError(f"processed {processed_id} не найден")

        key = uuid.uuid4().hex[:8]
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[key] = fut
        self._processed_ids[key] = processed_id

        msg = format_approval_message(processed, sources_count)
        await self._send(msg, key, processed_id)

        try:
            decision: str = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._cleanup(key)
            logger.warning("[approver] таймаут одобрения #%d", processed_id)
            return "timeout"

        if decision == "approve":
            kb.approve(processed_id)
            kb.log_sync("approve", "ok", f"processed={processed_id}")
            return "approved"
        if decision.startswith("reject"):
            reason = decision.partition(":")[2]
            kb.reject(processed_id, reason)
            kb.log_sync("reject", "ok", f"processed={processed_id} reason={reason}")
            return "rejected"
        return decision

    def resolve(self, key: str, decision: str) -> bool:
        """Закрыть ожидание: decision = 'approve' | 'reject[:причина]'."""
        fut = self._pending.pop(key, None)
        self._processed_ids.pop(key, None)
        if fut and not fut.done():
            fut.set_result(decision)
            return True
        return False

    async def revise(self, key: str, new_content: str) -> str:
        """📝 Правки: применить новый контент и переотправить план (тот же key
        закрывается, создаётся новый цикл ожидания)."""
        processed_id = self._processed_ids.get(key)
        if processed_id is None:
            raise ValueError(f"Ключ {key} не в ожидании")
        kb.update_content(processed_id, new_content)
        # закрыть старый Future без решения и запустить повторный цикл
        fut = self._pending.pop(key, None)
        self._processed_ids.pop(key, None)
        if fut and not fut.done():
            fut.cancel()
        return await self.submit(processed_id)

    def get_processed_id(self, key: str) -> int | None:
        return self._processed_ids.get(key)

    def _cleanup(self, key: str) -> None:
        self._pending.pop(key, None)
        self._processed_ids.pop(key, None)
