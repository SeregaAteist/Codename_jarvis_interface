"""AniList: mock GraphQL — найдено, не найдено, 429 retry; парсинг тайтла."""

import httpx
import respx
from agents.anilist_agent import (
    ANILIST_URL,
    _extract_search_title,
    enrich_with_anilist,
)

_MEDIA = {
    "id": 10,
    "idMal": 1,
    "title": {"romaji": "Test Anime", "english": "Test"},
    "averageScore": 85,
    "description": "<b>Desc</b> text",
    "genres": ["Action", "Fantasy"],
    "startDate": {"year": 2024},
}


def test_extract_search_title():
    assert _extract_search_title("Русское / Romaji Name [1-12 из 12]") == "Romaji Name"
    assert _extract_search_title("Просто название [5 из 24]") == "Просто название"


async def test_enrich_found():
    with respx.mock:
        respx.post(ANILIST_URL).mock(
            return_value=httpx.Response(200, json={"data": {"Media": _MEDIA}})
        )
        items = await enrich_with_anilist([{"title": "X / Test Anime [1]"}])
    item = items[0]
    assert item["mal_score"] == 8.5 and item["mal_id"] == 1
    assert item["synopsis"] == "Desc text"  # html вычищен
    assert item["genres"] == "Action, Fantasy"
    assert item["year"] == "2024"


async def test_enrich_not_found_keeps_item():
    with respx.mock:
        respx.post(ANILIST_URL).mock(
            return_value=httpx.Response(200, json={"data": {"Media": None}})
        )
        items = await enrich_with_anilist([{"title": "Неизвестное [1]"}])
    assert "mal_score" not in items[0]  # поле не появилось → fallback сработает


async def test_rate_limit_retry(monkeypatch):
    """429 → sleep → повтор → успех."""
    import agents.anilist_agent as mod

    slept = []

    async def fake_sleep(sec):
        slept.append(sec)

    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)

    with respx.mock:
        route = respx.post(ANILIST_URL)
        route.side_effect = [
            httpx.Response(429, json={}),
            httpx.Response(200, json={"data": {"Media": _MEDIA}}),
        ]
        items = await enrich_with_anilist([{"title": "Test [1]"}])
    assert items[0]["mal_score"] == 8.5
    assert 60 in slept
