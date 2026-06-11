"""Парсинг Reddit RSS (Atom, stdlib xml.etree).

ВАЖНО (расхождение с ТЗ): Reddit .rss НЕ содержит score/ups, а top.json отдаёт 403
без OAuth — поэтому фильтр score>50 и сортировка по score невозможны. Берём свежие
посты за N часов в порядке ленты (≈hot). Реальный score-рэнкинг = Reddit OAuth API.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

_NS = {"atom": "http://www.w3.org/2005/Atom"}
_UA = "Mozilla/5.0 (jarvis-briefing)"


def _parse_feed(xml_text: str, subreddit: str, limit: int = 5, hours: int = 24) -> list[dict]:
    """Чистый парсер (тестируемый без сети). Возвращает посты за последние `hours`."""
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        logger.warning("[reddit] %s: ошибка парсинга XML: %s", subreddit, e)
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    posts: list[dict] = []
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
        if dt and dt < cutoff:
            continue
        posts.append({
            "title": title, "url": url, "score": None,
            "created_utc": dt.timestamp() if dt else None, "subreddit": subreddit,
        })
        if len(posts) >= limit:
            break
    return posts


async def fetch_top_posts(subreddit: str, limit: int = 5, hours: int = 24) -> list[dict]:
    """Свежие посts сабреддита за `hours`. При ошибке — [] (не падать)."""
    import httpx

    url = f"https://www.reddit.com/r/{subreddit}/.rss"
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": _UA}) as cli:
            r = await cli.get(url)
            r.raise_for_status()
            return _parse_feed(r.text, subreddit, limit, hours)
    except Exception as e:
        logger.warning("[reddit] %s недоступен: %s", subreddit, e)
        return []
