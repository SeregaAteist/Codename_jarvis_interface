"""TG-уведомления о звонках: срочные → личка владельца, рабочие → топик группы."""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_USER_ID", "374728252"))


async def _send(chat_id: int, text: str, thread_id: int | None = None) -> None:
    payload: dict = {"chat_id": chat_id, "text": text,
                     "parse_mode": "HTML", "disable_web_page_preview": True}
    if thread_id:
        payload["message_thread_id"] = thread_id
    token = os.getenv("JARVIS_NOTIFY_BOT_TOKEN") or TG_TOKEN
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
        if r.status_code != 200:
            logger.error("[notifier] TG %s: %s", r.status_code, r.text[:200])


async def notify_call(phone: str, contact_name: str, lead_name: str, lead_url: str,
                      manager_name: str = "", is_urgent: bool = True) -> None:
    lines = [f"📞 Звонок: <b>{contact_name}</b>", f"📱 {phone}"]
    if manager_name:
        lines.append(f"👤 Менеджер: {manager_name}")
    lines.append(f"🔗 <a href='{lead_url}'>{lead_name}</a>")
    text = "\n".join(lines)

    if is_urgent:
        await _send(OWNER_ID, text)
    work_chat = os.getenv("WORK_CHAT_ID")
    work_topic = os.getenv("WORK_TOPIC_ID")
    if work_chat:
        await _send(int(work_chat), text,
                    thread_id=int(work_topic) if work_topic else None)
    logger.info("[notifier] %s → %s (менеджер: %s)", phone, lead_name, manager_name or "—")
