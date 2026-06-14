"""Kommo CRM API клиент."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from shared.config.settings import get_settings
from shared.models.kommo import KommoContact, KommoLead, KommoTask

logger = logging.getLogger(__name__)


class KommoClient:
    """Typed Kommo CRM клиент с Pydantic моделями.

    Пример использования:
        client = KommoClient()
        contact = await client.find_contact_by_phone("+380939151888")
        if contact:
            leads = await client.get_contact_leads(contact.id)
            print(f"Знайдено {len(leads)} угод")
    """

    def __init__(self, domain: str | None = None, token: str | None = None) -> None:
        s = get_settings()
        self._domain = domain or s.kommo_domain
        self._token = token or s.kommo_token
        self._base = f"https://{self._domain}/api/v4"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def find_contact_by_phone(self, phone: str) -> KommoContact | None:
        clean = "".join(filter(str.isdigit, phone))[-10:]
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{self._base}/contacts",
                headers=self._headers,
                params={"query": phone, "limit": 5},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        for contact in data.get("_embedded", {}).get("contacts", []):
            for field in contact.get("custom_fields_values") or []:
                for val in field.get("values", []):
                    if clean in "".join(filter(str.isdigit, str(val.get("value", "")))):
                        return KommoContact(
                            id=contact["id"], name=contact.get("name", phone)
                        )
        return None

    async def get_lead(self, lead_id: int) -> KommoLead | None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/leads/{lead_id}", headers=self._headers)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        fields = {k: data[k] for k in KommoLead.model_fields if k in data}
        return KommoLead(**fields)

    async def get_contact_leads(self, contact_id: int) -> list[KommoLead]:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{self._base}/contacts/{contact_id}",
                headers=self._headers,
                params={"with": "leads"},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        lead_stubs = data.get("_embedded", {}).get("leads", [])
        result: list[KommoLead] = []
        for stub in lead_stubs:
            lead = await self.get_lead(stub["id"])
            if lead:
                result.append(lead)
        return result

    async def create_task(
        self,
        lead_id: int,
        text: str,
        responsible_user_id: int,
        days: int = 1,
    ) -> KommoTask | None:
        due = int((datetime.now() + timedelta(days=days)).timestamp())
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{self._base}/tasks",
                headers=self._headers,
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
            r.raise_for_status()
        return None

    async def add_note(self, lead_id: int, text: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                f"{self._base}/leads/{lead_id}/notes",
                headers=self._headers,
                json=[{"note_type": "common", "params": {"text": text}}],
            )

    async def get_leads(
        self,
        limit: int = 50,
        page: int = 1,
        status_id: int | None = None,
    ) -> list[KommoLead]:
        params: dict[str, Any] = {"limit": limit, "page": page}
        if status_id is not None:
            params["filter[statuses][0][status_id]"] = status_id
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/leads", headers=self._headers, params=params)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        leads = data.get("_embedded", {}).get("leads", [])
        return [
            KommoLead(**{k: lead[k] for k in KommoLead.model_fields if k in lead})
            for lead in leads
        ]

    async def get_users(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/users", headers=self._headers)
            r.raise_for_status()
            return r.json().get("_embedded", {}).get("users", [])

    async def get_pipelines(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/leads/pipelines", headers=self._headers)
            r.raise_for_status()
            return r.json().get("_embedded", {}).get("pipelines", [])

    async def search_leads(self, query: str, limit: int = 10) -> list[KommoLead]:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{self._base}/leads",
                headers=self._headers,
                params={"query": query, "limit": limit},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        leads = data.get("_embedded", {}).get("leads", [])
        return [
            KommoLead(**{k: lead[k] for k in KommoLead.model_fields if k in lead})
            for lead in leads
        ]

    async def get_stale_leads(
        self, days_inactive: int = 7, limit: int = 50
    ) -> list[KommoLead]:
        cutoff = int((datetime.now() - timedelta(days=days_inactive)).timestamp())
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{self._base}/leads",
                headers=self._headers,
                params={"limit": limit, "filter[updated_at][to]": cutoff},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        leads = data.get("_embedded", {}).get("leads", [])
        return [
            KommoLead(**{k: lead[k] for k in KommoLead.model_fields if k in lead})
            for lead in leads
        ]

    def get_lead_url(self, lead_id: int) -> str:
        return f"https://{self._domain}/leads/detail/{lead_id}"


# ── Backward-compatible функции (используются webhook.py до Шага 4) ──────────

_DOMAIN = os.getenv("KOMMO_DOMAIN", "lkenergy.kommo.com")
_BASE = f"https://{_DOMAIN}/api/v4"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.getenv('KOMMO_TOKEN', '')}"}


async def find_contact_by_phone(phone: str) -> dict[str, Any] | None:
    clean = "".join(filter(str.isdigit, phone))[-10:]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{_BASE}/contacts",
            headers=_headers(),
            params={"query": phone, "limit": 5},
        )
        data: dict[str, Any] = r.json()
    for contact in data.get("_embedded", {}).get("contacts", []):
        for field in contact.get("custom_fields_values") or []:
            for val in field.get("values", []):
                if clean in "".join(filter(str.isdigit, str(val.get("value", "")))):
                    return contact  # type: ignore[return-value]
    return None


async def find_lead_by_contact(contact_id: int) -> dict[str, Any] | None:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{_BASE}/contacts/{contact_id}",
            headers=_headers(),
            params={"with": "leads"},
        )
        data: dict[str, Any] = r.json()
    leads = data.get("_embedded", {}).get("leads", [])
    if not leads:
        return None
    lead_id = leads[-1]["id"]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{_BASE}/leads/{lead_id}", headers=_headers())
        return r.json()  # type: ignore[return-value]


async def get_lead_link(lead: dict[str, Any]) -> str:
    return f"https://{_DOMAIN}/leads/detail/{lead['id']}"
