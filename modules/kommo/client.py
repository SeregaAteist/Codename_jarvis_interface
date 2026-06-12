"""Kommo API client."""
from __future__ import annotations
import logging
import os
import httpx

logger = logging.getLogger(__name__)

DOMAIN = os.getenv("KOMMO_DOMAIN", "lkenergy.kommo.com")
BASE = f"https://{DOMAIN}/api/v4"


def _headers() -> dict:
    # токен читается при вызове, не при импорте — иначе пустой до load_dotenv
    return {"Authorization": f"Bearer {os.getenv('KOMMO_TOKEN', '')}"}


async def find_contact_by_phone(phone: str) -> dict | None:
    """Найти контакт по номеру телефона."""
    clean = "".join(filter(str.isdigit, phone))[-10:]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/contacts",
            headers=_headers(),
            params={"query": phone, "limit": 5})
        data = r.json()
    contacts = data.get("_embedded", {}).get("contacts", [])
    for contact in contacts:
        for field in contact.get("custom_fields_values") or []:
            for val in field.get("values", []):
                if clean in "".join(filter(str.isdigit, str(val.get("value","")))):
                    return contact
    return None


async def find_lead_by_contact(contact_id: int) -> dict | None:
    """Последняя активная сделка контакта."""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/contacts/{contact_id}",
            headers=_headers(),
            params={"with": "leads"})
        data = r.json()
    leads = data.get("_embedded", {}).get("leads", [])
    if not leads:
        return None
    lead_id = leads[-1]["id"]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BASE}/leads/{lead_id}",
            headers=_headers())
        return r.json()


async def get_lead_link(lead: dict) -> str:
    """Ссылка на сделку в Kommo."""
    return f"https://{DOMAIN}/leads/detail/{lead['id']}"
