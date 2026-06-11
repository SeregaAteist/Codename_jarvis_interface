"""ParserDispatcher — читает sources/<file>.yaml, запускает нужный парсер параллельно.

Новый источник = новая запись в sources/*.yaml, без изменения кода.
"""
from __future__ import annotations

import asyncio
import logging

import yaml

from core.parsers.api import ApiParser
from core.parsers.html import HtmlParser
from core.parsers.rss import RssParser
from shared.config.base import ROOT

logger = logging.getLogger(__name__)
SOURCES_DIR = ROOT / "sources"


def _load_sources(file: str = "anime") -> dict:
    p = SOURCES_DIR / f"{file}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


class ParserDispatcher:
    def __init__(self, sources_file: str = "anime"):
        self.sources = (_load_sources(sources_file) or {}).get("sources", {})

    async def run(self, source_name: str) -> list[dict]:
        src = self.sources.get(source_name)
        if not src:
            logger.warning("[dispatcher] нет источника '%s'", source_name)
            return []
        ptype = src.get("parser", "api")
        try:
            if ptype == "api":
                base = src.get("api_url") or src.get("base_url", "")
                last = src.get("endpoints", {}).get("last", "/last")
                limit = int(src.get("limit", 20))
                data = await ApiParser(int(src.get("timeout", 30))).fetch(
                    base + last, params={"page": 1, "quantity": limit})
                items = data.get("data", data) if isinstance(data, dict) else data
                return items if isinstance(items, list) else []
            if ptype == "rss":
                return await RssParser().fetch(src.get("url", ""), source=source_name)
            if ptype == "html":
                return await HtmlParser().fetch(src.get("base_url", ""), src.get("selector"))
        except Exception as e:
            logger.error("[dispatcher] '%s' (%s) упал: %s", source_name, ptype, e)
            return []
        return []

    async def run_many(self, names: list[str]) -> list[dict]:
        results = await asyncio.gather(*(self.run(n) for n in names), return_exceptions=True)
        out: list[dict] = []
        for r in results:
            if isinstance(r, list):
                out.extend(r)
        return out
