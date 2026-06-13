"""TG-уведомления о звонках: срочные → личка владельца, рабочие → топик группы."""

from __future__ import annotations

import logging
import os

import httpx

from shared.config.settings import get_settings

logger = logging.getLogger(__name__)


class CallNotifier:
    """Отправляет уведомления о звонках через нужного Telegram-бота."""

    def __init__(self) -> None:
        s = get_settings()
        self._owner_id = s.owner_user_id
        self._notify_token = s.jarvis_notify_bot_token or s.telegram_bot_token
        self._work_token = s.jarvis_work_bot_token or self._notify_token
        self._work_chat = s.work_chat_id
        self._work_topic = s.work_topic_id

    async def _send(
        self,
        chat_id: int,
        text: str,
        thread_id: int | None = None,
        token: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if thread_id:
            payload["message_thread_id"] = thread_id
        _token = token or self._notify_token
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{_token}/sendMessage", json=payload
            )
            if r.status_code != 200:
                logger.error("[notifier] TG %s: %s", r.status_code, r.text[:200])

    async def notify_call(
        self,
        phone: str,
        contact_name: str,
        lead_name: str,
        lead_url: str,
        manager_name: str = "",
        is_urgent: bool = True,
    ) -> None:
        lines = [f"📞 Звонок: <b>{contact_name}</b>", f"📱 {phone}"]
        if manager_name:
            lines.append(f"👤 Менеджер: {manager_name}")
        lines.append(f"🔗 <a href='{lead_url}'>{lead_name}</a>")
        text = "\n".join(lines)

        if is_urgent:
            await self._send(self._owner_id, text, token=self._notify_token)
        else:
            await self._send(
                self._work_chat,
                text,
                thread_id=self._work_topic,
                token=self._work_token,
            )
        logger.info(
            "[notifier] %s → %s urgent=%s (менеджер: %s)",
            phone,
            lead_name,
            is_urgent,
            manager_name or "—",
        )

    async def notify_unknown(self, phone: str) -> None:
        text = f"📞 Неизвестный номер: <b>{phone}</b>\nКонтакт не найден в Kommo"
        await self._send(self._owner_id, text, token=self._notify_token)


# ── Backward-compatible функция (используется при прямом вызове) ──────────────

_TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_OWNER_ID = int(os.getenv("OWNER_USER_ID", "374728252"))


async def _send(
    chat_id: int, text: str, thread_id: int | None = None, token: str | None = None
) -> None:
    payload: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id
    _token = token or os.getenv("JARVIS_NOTIFY_BOT_TOKEN") or _TG_TOKEN
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"https://api.telegram.org/bot{_token}/sendMessage", json=payload
        )
        if r.status_code != 200:
            logger.error("[notifier] TG %s: %s", r.status_code, r.text[:200])


async def notify_call(
    phone: str,
    contact_name: str,
    lead_name: str,
    lead_url: str,
    manager_name: str = "",
    is_urgent: bool = True,
) -> None:
    lines = [f"📞 Звонок: <b>{contact_name}</b>", f"📱 {phone}"]
    if manager_name:
        lines.append(f"👤 Менеджер: {manager_name}")
    lines.append(f"🔗 <a href='{lead_url}'>{lead_name}</a>")
    text = "\n".join(lines)

    if is_urgent:
        await _send(_OWNER_ID, text)
    else:
        work_token = (
            os.getenv("JARVIS_WORK_BOT_TOKEN")
            or os.getenv("JARVIS_NOTIFY_BOT_TOKEN")
            or _TG_TOKEN
        )
        work_chat = os.getenv("WORK_CHAT_ID")
        work_topic = os.getenv("WORK_TOPIC_ID")
        if work_chat:
            await _send(
                int(work_chat),
                text,
                thread_id=int(work_topic) if work_topic else None,
                token=work_token,
            )
    logger.info(
        "[notifier] %s → %s urgent=%s (менеджер: %s)",
        phone,
        lead_name,
        is_urgent,
        manager_name or "—",
    )
