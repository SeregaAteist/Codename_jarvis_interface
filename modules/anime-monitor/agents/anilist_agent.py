import asyncio
import logging
import re

import httpx

from agents.base_enricher import BaseEnricher
from config import cfg

logger = logging.getLogger("anilist")

ANILIST_URL = "https://graphql.anilist.co"

QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
    id
    idMal
    title { romaji english }
    averageScore
    description(asHtml: false)
    genres
    startDate { year }
  }
}
"""


def _extract_search_title(raw_title: str) -> str:
    # "Русское название / Romaji Name [1-12 из 12]" → "Romaji Name"
    if " / " in raw_title:
        part = raw_title.split(" / ")[-1]
    else:
        part = raw_title
    part = re.sub(r"\s*\[.*$", "", part).strip()
    return part or raw_title[:60]


async def _query_media(client: httpx.AsyncClient, search: str) -> dict | None:
    resp = await client.post(
        ANILIST_URL,
        json={"query": QUERY, "variables": {"search": search}},
    )
    if resp.status_code == 429:
        logger.warning("Rate limit — ждём 60 сек...")
        await asyncio.sleep(60)
        resp = await client.post(
            ANILIST_URL,
            json={"query": QUERY, "variables": {"search": search}},
        )
    return resp.json().get("data", {}).get("Media")


async def _enrich_one(client: httpx.AsyncClient, item: dict) -> None:
    search = _extract_search_title(item["title"])
    try:
        media = await _query_media(client, search)
        if not media:
            logger.info("✗ не найден: %s", search[:40])
            return
        score = media.get("averageScore")
        item["mal_id"] = media.get("idMal")
        item["mal_score"] = round(score / 10, 1) if score else None
        raw_desc = media.get("description") or ""
        item["synopsis"] = re.sub(r"<[^>]+>", "", raw_desc)[:500]
        item["genres"] = ", ".join(media.get("genres", [])[:4])
        if not item.get("year"):
            y = (media.get("startDate") or {}).get("year")
            if y:
                item["year"] = str(y)
        logger.info("✓ %s → %s", search[:40], item.get("mal_score", "—"))
    except Exception as e:
        logger.error("Ошибка '%s': %s", search[:40], e)


async def enrich_with_anilist(items: list[dict]) -> list[dict]:
    """Батчи по ENRICH_BATCH_SIZE параллельно, пауза между батчами — под rate limit."""
    async with httpx.AsyncClient(timeout=12) as client:
        bs = cfg.ENRICH_BATCH_SIZE
        for start in range(0, len(items), bs):
            batch = items[start:start + bs]
            await asyncio.gather(*(_enrich_one(client, i) for i in batch))
            if start + bs < len(items):
                await asyncio.sleep(cfg.ANILIST_BATCH_PAUSE)
    return items


class AniListEnricher(BaseEnricher):
    name = "anilist"
    priority = 0

    async def enrich(self, items: list[dict]) -> list[dict]:
        return await enrich_with_anilist(items)
