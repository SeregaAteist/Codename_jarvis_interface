import asyncio
import logging

import httpx
from config import cfg

from agents.base_enricher import BaseEnricher

logger = logging.getLogger("jikan")


async def _enrich_one(client: httpx.AsyncClient, item: dict) -> None:
    mal_data = await _search_mal(client, item.get("title", ""))
    if not mal_data:
        return
    item["mal_score"] = mal_data.get("score")
    item["mal_id"] = mal_data.get("mal_id")
    item["synopsis"] = (mal_data.get("synopsis") or "")[:300]
    if not item.get("genres"):
        genres = mal_data.get("genres", [])
        item["genres"] = ", ".join(g["name"] for g in genres[:4])
    if not item.get("img_url") and mal_data.get("images"):
        item["img_url"] = mal_data["images"].get("jpg", {}).get("image_url", "")


async def enrich_with_jikan(items: list[dict]) -> list[dict]:
    """Батчи по ENRICH_BATCH_SIZE параллельно (лимит Jikan 3 req/sec)."""
    async with httpx.AsyncClient(timeout=10) as client:
        bs = cfg.ENRICH_BATCH_SIZE
        for start in range(0, len(items), bs):
            batch = items[start : start + bs]
            await asyncio.gather(*(_enrich_one(client, i) for i in batch))
            if start + bs < len(items):
                await asyncio.sleep(cfg.JIKAN_BATCH_PAUSE)
    return items


async def _search_mal(client: httpx.AsyncClient, title: str) -> dict | None:
    clean = _clean_title(title)
    try:
        resp = await client.get(
            f"{cfg.JIKAN_URL}/anime", params={"q": clean, "limit": 1, "sfw": True}
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data[0] if data else None
    except Exception as e:
        logger.error("Ошибка для '%s': %s", clean, e)
        return None


def _clean_title(title: str) -> str:
    stop = [
        "Смотреть",
        "онлайн",
        "все серии",
        "серия",
        "субтитры",
        "озвучка",
        "HD",
        "1080",
        "720",
    ]
    result = title
    for word in stop:
        result = result.replace(word, "")
    return result.strip()[:60]


class JikanEnricher(BaseEnricher):
    name = "jikan"
    priority = 1  # fallback после AniList

    async def enrich(self, items: list[dict]) -> list[dict]:
        return await enrich_with_jikan(items)
