"""Jikan: _clean_title, mock REST, fallback-условие needs_enrichment."""
import httpx
import respx

from agents.jikan_agent import JikanEnricher, _clean_title, enrich_with_jikan
from config import cfg


def test_clean_title():
    assert _clean_title("Наруто Смотреть онлайн все серии HD") == "Наруто"
    assert len(_clean_title("х" * 200)) <= 60


def test_needs_enrichment_fallback():
    e = JikanEnricher()
    assert e.priority == 1                              # после AniList
    assert e.needs_enrichment({"title": "X"})           # mal_score нет
    assert not e.needs_enrichment({"mal_score": 8.0})   # AniList уже заполнил


async def test_enrich_fills_fields():
    payload = {"data": [{
        "mal_id": 5, "score": 7.7, "synopsis": "s" * 500,
        "genres": [{"name": "Action"}, {"name": "Drama"}],
        "images": {"jpg": {"image_url": "https://img/x.jpg"}},
    }]}
    with respx.mock:
        respx.get(f"{cfg.JIKAN_URL}/anime").mock(
            return_value=httpx.Response(200, json=payload))
        items = await enrich_with_jikan([{"title": "Тест", "genres": ""}])
    item = items[0]
    assert item["mal_score"] == 7.7 and item["mal_id"] == 5
    assert len(item["synopsis"]) == 300
    assert item["genres"] == "Action, Drama"
    assert item["img_url"] == "https://img/x.jpg"


async def test_enrich_survives_error():
    with respx.mock:
        respx.get(f"{cfg.JIKAN_URL}/anime").mock(
            return_value=httpx.Response(500))
        items = await enrich_with_jikan([{"title": "Тест"}])
    assert "mal_score" not in items[0]   # ошибка не роняет pipeline
