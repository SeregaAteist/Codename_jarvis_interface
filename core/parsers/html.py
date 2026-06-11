"""HtmlParser — HTML scraping (BeautifulSoup). Fallback если API недоступен.

bs4/lxml импортируются лениво — модуль импортируется даже без них.
"""
from __future__ import annotations

import logging

from core.parsers.base import _UA, BaseParser

logger = logging.getLogger(__name__)


class HtmlParser(BaseParser):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def fetch(self, url: str, selector: str | None = None):
        import httpx
        from bs4 import BeautifulSoup  # lazy: bs4 нужен только для html-пути

        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": _UA}) as cli:
            r = await cli.get(url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
        if selector:
            return [{"text": el.get_text(strip=True), "html": str(el)} for el in soup.select(selector)]
        return {"title": soup.title.get_text(strip=True) if soup.title else "", "url": url}
