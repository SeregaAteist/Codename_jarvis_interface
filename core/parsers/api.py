"""ApiParser — REST/JSON источники (Animevost API). httpx, без авторизации."""
from __future__ import annotations

import logging

from core.parsers.base import _UA, BaseParser

logger = logging.getLogger(__name__)


class ApiParser(BaseParser):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def fetch(self, url: str, params: dict | None = None):
        import httpx
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": _UA}) as cli:
            r = await cli.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def post(self, url: str, data: dict | None = None):
        import httpx
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": _UA}) as cli:
            r = await cli.post(url, data=data)
            r.raise_for_status()
            return r.json()
