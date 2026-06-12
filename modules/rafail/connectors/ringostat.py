"""RingostatConnector — транскрипты звонков (RF-6).

.env:
    RINGOSTAT_TOKEN=    # API ключ проекта
    RINGOSTAT_PROJECT=  # id проекта
"""
from __future__ import annotations

import logging

from shared.config.secrets import opt

logger = logging.getLogger(__name__)

_API = "https://api.ringostat.com"


class RingostatConnector:
    def __init__(self, token: str = "", project: str = "", timeout: int = 30):
        self.token = token or opt("RINGOSTAT_TOKEN")
        self.project = project or opt("RINGOSTAT_PROJECT")
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.token and self.project)

    async def _get(self, path: str, params: dict | None = None):
        import httpx
        params = {"auth_key": self.token, "project": self.project, **(params or {})}
        async with httpx.AsyncClient(timeout=self.timeout) as cli:
            r = await cli.get(f"{_API}{path}", params=params)
            r.raise_for_status()
            return r.json()

    async def get_calls(self, limit: int = 20) -> list[dict]:
        """Последние звонки проекта."""
        if not self.is_configured():
            raise RuntimeError("Ringostat: задайте RINGOSTAT_TOKEN и RINGOSTAT_PROJECT в .env")
        data = await self._get("/statistics/calls", params={"limit": limit})
        return data.get("data", []) if isinstance(data, dict) else []

    async def get_transcripts(self, limit: int = 20) -> list[dict]:
        """Звонки с транскриптами: [{id, title, transcript}]."""
        calls = await self.get_calls(limit=limit)
        out = []
        for c in calls:
            transcript = c.get("transcription") or c.get("transcript") or ""
            if not transcript:
                continue
            out.append({
                "id": c.get("id") or c.get("call_id"),
                "title": f"Звонок {c.get('caller', '')} → {c.get('called', '')}",
                "transcript": transcript,
            })
        return out
