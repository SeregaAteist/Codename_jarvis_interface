"""Kommo contacts — работа с контактами."""

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


async def find_by_phone(phone: str) -> dict | None:
    clean = "".join(filter(str.isdigit, phone))[-10:]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{BASE}/contacts", headers=_headers(), params={"query": phone, "limit": 5}
        )
        contacts = r.json().get("_embedded", {}).get("contacts", [])
    for contact in contacts:
        for field in contact.get("custom_fields_values") or []:
            for val in field.get("values", []):
                if clean in "".join(filter(str.isdigit, str(val.get("value", "")))):
                    return contact
    return None


async def get_contact_leads(contact_id: int) -> list:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{BASE}/contacts/{contact_id}",
            headers=_headers(),
            params={"with": "leads"},
        )
        return r.json().get("_embedded", {}).get("leads", [])


async def create_contact(name: str, phone: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{BASE}/contacts",
            headers=_headers(),
            json=[
                {
                    "name": name,
                    "custom_fields_values": [
                        {"field_code": "PHONE", "values": [{"value": phone}]}
                    ],
                }
            ],
        )
        return r.json()
