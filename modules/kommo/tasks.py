"""Kommo tasks API — создание задач в сделках."""
from __future__ import annotations
import logging, os, httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
DOMAIN = os.getenv("KOMMO_DOMAIN", "lkenergy.kommo.com")
TOKEN = os.getenv("KOMMO_TOKEN", "")
BASE = f"https://{DOMAIN}/api/v4"

async def create_task(lead_id: int, text: str, responsible_user_id: int, days_until_due: int = 1) -> dict:
    due = int((datetime.now() + timedelta(days=days_until_due)).timestamp())
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{BASE}/tasks",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json=[{"task_type_id": 1, "text": text, "complete_till": due,
                   "entity_type": "leads", "entity_id": lead_id,
                   "responsible_user_id": responsible_user_id}])
        return r.json()

async def get_stale_leads(days_inactive: int = 7, limit: int = 50) -> list:
    cutoff = int((datetime.now() - timedelta(days=days_inactive)).timestamp())
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/leads",
            headers={"Authorization": f"Bearer {TOKEN}"},
            params={"limit": limit, "filter[updated_at][to]": cutoff})
        return r.json().get("_embedded", {}).get("leads", [])
