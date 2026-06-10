import asyncio
import re
import httpx

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


async def enrich_with_anilist(items: list[dict]) -> list[dict]:
    enriched = []
    async with httpx.AsyncClient(timeout=12) as client:
        for i, item in enumerate(items):
            search = _extract_search_title(item["title"])
            try:
                resp = await client.post(
                    ANILIST_URL,
                    json={"query": QUERY, "variables": {"search": search}},
                )
                if resp.status_code == 429:
                    print(f"[AniList] Rate limit — ждём 60 сек...")
                    await asyncio.sleep(60)
                    resp = await client.post(
                        ANILIST_URL,
                        json={"query": QUERY, "variables": {"search": search}},
                    )
                data = resp.json()
                media = data.get("data", {}).get("Media")
                if media:
                    score = media.get("averageScore")
                    item["mal_id"]   = media.get("idMal")
                    item["mal_score"] = round(score / 10, 1) if score else None
                    raw_desc = media.get("description") or ""
                    item["synopsis"] = re.sub(r"<[^>]+>", "", raw_desc)[:500]
                    if not item.get("year"):
                        y = (media.get("startDate") or {}).get("year")
                        if y:
                            item["year"] = str(y)
                    print(f"[AniList] {i+1}/{len(items)} ✓ {search[:40]} → {item.get('mal_score', '—')}")
                else:
                    print(f"[AniList] {i+1}/{len(items)} ✗ не найден: {search[:40]}")
            except Exception as e:
                print(f"[AniList] Ошибка '{search[:40]}': {e}")

            enriched.append(item)

            # ~1.5 req/sec (well under 90/min limit)
            await asyncio.sleep(0.7)

    return enriched
