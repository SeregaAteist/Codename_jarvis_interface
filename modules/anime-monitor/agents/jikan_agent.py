import asyncio
import httpx
from config import cfg


async def enrich_with_jikan(items: list[dict]) -> list[dict]:
    enriched = []
    async with httpx.AsyncClient(timeout=10) as client:
        for item in items:
            title = item.get("title", "")
            mal_data = await _search_mal(client, title)
            if mal_data:
                item["mal_score"] = mal_data.get("score")
                item["mal_id"] = mal_data.get("mal_id")
                item["synopsis"] = (mal_data.get("synopsis") or "")[:300]
                if not item.get("genres"):
                    genres = mal_data.get("genres", [])
                    item["genres"] = ", ".join(
                        g["name"] for g in genres[:4]
                    )
                if not item.get("img_url") and mal_data.get("images"):
                    item["img_url"] = (
                        mal_data["images"].get("jpg", {}).get("image_url", "")
                    )
            enriched.append(item)
            await asyncio.sleep(1.2)
    return enriched


async def _search_mal(
    client: httpx.AsyncClient, title: str
) -> dict | None:
    clean = _clean_title(title)
    try:
        resp = await client.get(
            f"{cfg.JIKAN_URL}/anime",
            params={"q": clean, "limit": 1, "sfw": True}
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data[0] if data else None
    except Exception as e:
        print(f"[Jikan] Ошибка для '{clean}': {e}")
        return None


def _clean_title(title: str) -> str:
    stop = [
        "Смотреть", "онлайн", "все серии", "серия",
        "субтитры", "озвучка", "HD", "1080", "720"
    ]
    result = title
    for word in stop:
        result = result.replace(word, "")
    return result.strip()[:60]
