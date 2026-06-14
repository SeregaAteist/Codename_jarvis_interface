"""Kommo tasks API — создание задач в сделках и реанимация старых лидов."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)
DOMAIN = os.getenv("KOMMO_DOMAIN", "lkenergy.kommo.com")
BASE = f"https://{DOMAIN}/api/v4"

WORK_TOPIC_ID = int(os.getenv("WORK_TOPIC_ID", "202"))


def _headers() -> dict:
    # токен читается при вызове, не при импорте — иначе пустой до load_dotenv
    return {"Authorization": f"Bearer {os.getenv('KOMMO_TOKEN', '')}"}


async def create_task(
    lead_id: int, text: str, responsible_user_id: int, days_until_due: int = 1
) -> dict:
    due = int((datetime.now() + timedelta(days=days_until_due)).timestamp())
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{BASE}/tasks",
            headers=_headers(),
            json=[
                {
                    "task_type_id": 1,
                    "text": text,
                    "complete_till": due,
                    "entity_type": "leads",
                    "entity_id": lead_id,
                    "responsible_user_id": responsible_user_id,
                }
            ],
        )
        return r.json()


async def get_stale_leads(days_inactive: int = 7, limit: int = 50) -> list:
    cutoff = int((datetime.now() - timedelta(days=days_inactive)).timestamp())
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{BASE}/leads",
            headers=_headers(),
            params={"limit": limit, "filter[updated_at][to]": cutoff},
        )
        return r.json().get("_embedded", {}).get("leads", [])


async def analyze_stale_leads(days_inactive: int = 7) -> list[dict]:
    """Найти сделки без активности и создать задачи на реанимацию.

    Пример использования:
        results = await analyze_stale_leads(days_inactive=7)
        print(f"Створено задач: {len(results)}")
    """
    # Импорт внутри функции чтобы избежать циклических зависимостей при старте
    from modules.kommo.client import KommoClient

    client = KommoClient()
    stale = await get_stale_leads(days_inactive=days_inactive)

    results = []
    for lead in stale:
        task_text = (
            f"Реанімація угоди. "
            f"Не було активності {days_inactive}+ днів. "
            f"Зателефонувати та уточнити статус."
        )
        try:
            await client.create_task(
                lead_id=lead["id"],
                text=task_text,
                responsible_user_id=lead.get("responsible_user_id", 0),
                days=1,
            )
            results.append(
                {
                    "lead_id": lead["id"],
                    "lead_name": lead.get("name", ""),
                    "days_inactive": days_inactive,
                }
            )
        except Exception as e:
            logger.error("[kommo] create_task lead=%s: %s", lead.get("id"), e)

    return results


async def _notify_tg(text: str) -> None:
    """Отправить результат реанимации в TG топик Work."""
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("GROUP_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.info("[kommo-reactivation] TG не настроен, пропускаем.")
        return
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if WORK_TOPIC_ID:
        payload["message_thread_id"] = WORK_TOPIC_ID
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)


async def run_reactivation(days_inactive: int = 7) -> None:
    """Точка входа для launchd: анализ + уведомление в TG."""
    results = await analyze_stale_leads(days_inactive=days_inactive)
    if not results:
        logger.info("[kommo-reactivation] Немає угод для реанімації.")
        return

    lines = [f"📋 <b>Kommo реанімація</b> — {datetime.now():%d.%m.%Y}\n"]
    lines.append(
        f"Знайдено {len(results)} угод без активності {days_inactive}+ днів:\n"
    )
    for r in results[:20]:
        lines.append(f"• <b>{r['lead_name'] or 'Без назви'}</b> (id {r['lead_id']})")
    if len(results) > 20:
        lines.append(f"...та ще {len(results) - 20} угод")

    await _notify_tg("\n".join(lines))
    logger.info("[kommo-reactivation] Оброблено %d угод.", len(results))


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    asyncio.run(run_reactivation())
