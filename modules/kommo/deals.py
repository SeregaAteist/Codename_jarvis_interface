"""Kommo deals — работа со сделками."""
from __future__ import annotations
import logging, os, httpx

logger = logging.getLogger(__name__)
DOMAIN = os.getenv("KOMMO_DOMAIN", "lkenergy.kommo.com")
TOKEN = os.getenv("KOMMO_TOKEN", "")
BASE = f"https://{DOMAIN}/api/v4"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

async def get_lead(lead_id: int) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/leads/{lead_id}", headers=HEADERS)
        return r.json()

async def get_leads(limit: int = 50, page: int = 1, **filters) -> list:
    params = {"limit": limit, "page": page, **filters}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/leads", headers=HEADERS, params=params)
        return r.json().get("_embedded", {}).get("leads", [])

async def update_lead(lead_id: int, **fields) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.patch(f"{BASE}/leads/{lead_id}", headers=HEADERS, json=fields)
        return r.json()

async def add_note(lead_id: int, text: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{BASE}/leads/{lead_id}/notes", headers=HEADERS,
            json=[{"note_type": "common", "params": {"text": text}}])
        return r.json()
