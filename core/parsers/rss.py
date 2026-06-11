"""RssParser — универсальный RSS/Atom (обобщение логики из briefing/reddit_rss).

Парсит Atom-ленту → list[{title, url, published, source}]. Фильтр по свежести (hours).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from core.parsers.base import _UA, BaseParser

logger = logging.getLogger(__name__)
_NS = {"atom": "http://www.w3.org/2005/Atom"}


def parse_atom(xml_text: str, source: str = "", limit: int = 20, hours: int | None = None) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        logger.warning("[rss] %s: ошибка XML: %s", source, e)
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None
    out: list[dict] = []
    for entry in root.findall("atom:entry", _NS):
        title = (entry.findtext("atom:title", default="", namespaces=_NS) or "").strip()
        link_el = entry.find("atom:link", _NS)
        url = link_el.get("href") if link_el is not None else ""
        published = (entry.findtext("atom:published", default="", namespaces=_NS)
                     or entry.findtext("atom:updated", default="", namespaces=_NS))
        dt = None
        try:
            if published:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except Exception:
            dt = None
        if cutoff and dt and dt < cutoff:
            continue
        out.append({"title": title, "url": url,
                    "published": dt.isoformat() if dt else None, "source": source})
        if len(out) >= limit:
            break
    return out


def parse_rss2(xml_text: str, source: str = "", limit: int = 20, hours: int | None = None) -> list[dict]:
    """RSS 2.0 (<rss><channel><item>) → тот же формат, что parse_atom."""
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        logger.warning("[rss] %s: ошибка XML: %s", source, e)
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None
    out: list[dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        published = item.findtext("pubDate") or ""
        dt = None
        try:
            if published:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(published)
        except Exception:
            dt = None
        if cutoff and dt and dt < cutoff:
            continue
        out.append({"title": title, "url": url,
                    "published": dt.isoformat() if dt else None, "source": source})
        if len(out) >= limit:
            break
    return out


def parse_feed(xml_text: str, source: str = "", limit: int = 20, hours: int | None = None) -> list[dict]:
    """Автоопределение формата: Atom или RSS 2.0."""
    if "<rss" in xml_text[:500]:
        return parse_rss2(xml_text, source, limit, hours)
    return parse_atom(xml_text, source, limit, hours)


class RssParser(BaseParser):
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def fetch(self, url: str, hours: int | None = 24, limit: int = 20, source: str = "") -> list[dict]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": _UA}) as cli:
                r = await cli.get(url)
                r.raise_for_status()
                return parse_feed(r.text, source or url, limit, hours)
        except Exception as e:
            logger.warning("[rss] %s недоступен: %s", url, e)
            return []
