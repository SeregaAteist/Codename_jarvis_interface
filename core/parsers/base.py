"""BaseParser — абстракция парсера источника."""
from __future__ import annotations

import asyncio

_UA = "Mozilla/5.0 (jarvis-anime)"


class BaseParser:
    async def fetch(self, url: str, **kwargs):
        raise NotImplementedError

    async def fetch_many(self, urls: list[str]) -> list:
        """Параллельный fetch (ошибка одного не роняет остальные)."""
        return await asyncio.gather(*(self.fetch(u) for u in urls), return_exceptions=True)
