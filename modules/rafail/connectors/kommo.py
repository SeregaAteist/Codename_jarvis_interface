"""KommoConnector — чтение сделок из Kommo CRM (RF-6).

.env:
    KOMMO_SUBDOMAIN=  # <subdomain>.kommo.com
    KOMMO_TOKEN=      # долгоживущий access token
"""
from __future__ import annotations

import logging

from shared.config.secrets import opt

logger = logging.getLogger(__name__)


class KommoConnector:
    def __init__(self, subdomain: str = "", token: str = "", timeout: int = 30):
        self.subdomain = subdomain or opt("KOMMO_SUBDOMAIN")
        self.token = token or opt("KOMMO_TOKEN")
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"https://{self.subdomain}.kommo.com/api/v4"

    def is_configured(self) -> bool:
        return bool(self.subdomain and self.token)

    async def _get(self, path: str, params: dict | None = None):
        import httpx
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.token}"},
        ) as cli:
            r = await cli.get(f"{self.base_url}{path}", params=params)
            r.raise_for_status()
            return r.json() if r.content else {}

    async def get_won_deals(self, limit: int = 20) -> list[dict]:
        """Успешно закрытые сделки (статус 142 = won в Kommo)."""
        if not self.is_configured():
            raise RuntimeError("Kommo: задайте KOMMO_SUBDOMAIN и KOMMO_TOKEN в .env")
        data = await self._get(
            "/leads",
            params={"filter[statuses][0][status_id]": 142, "limit": limit, "with": "contacts"},
        )
        return data.get("_embedded", {}).get("leads", [])

    async def get_lead_notes(self, lead_id: int, limit: int = 50) -> list[dict]:
        """Заметки сделки — история переговоров для case_study."""
        data = await self._get(f"/leads/{lead_id}/notes", params={"limit": limit})
        return data.get("_embedded", {}).get("notes", [])
