"""Рекомендации (A-7): через shared/llm router (мок), сборка промпта."""
import agents.recommend_agent as rec
from agents import db_agent as db


def test_build_prompt_contains_data():
    prompt = rec.build_prompt(
        [{"title": "Атака титанов", "status": "completed"}],
        [{"title": "Кандидат", "genres": "фэнтези", "mal_score": 8.2}],
    )
    assert "Атака титанов" in prompt and "Кандидат" in prompt


async def test_recommendations_use_router(tmp_db, monkeypatch):
    db.add_to_watchlist("Атака титанов")
    db.upsert_anime([{"title": "Кандидат", "url": "https://x/9",
                      "episode": "1", "genres": "фэнтези"}])

    called = {}

    async def fake_generate(prompt):
        called["prompt"] = prompt
        return "Советую: Кандидат"
    monkeypatch.setattr(rec, "_llm_generate", fake_generate)

    out = await rec.get_recommendations()
    assert "Кандидат" in out
    assert "Атака титанов" in called["prompt"]   # вотчлист попал в промпт


async def test_empty_watchlist_message(tmp_db):
    out = await rec.get_recommendations()
    assert "пуст" in out


async def test_llm_error_graceful(tmp_db, monkeypatch):
    db.add_to_watchlist("Тайтл")

    async def boom(prompt):
        raise RuntimeError("нет сети")
    monkeypatch.setattr(rec, "_llm_generate", boom)

    out = await rec.get_recommendations()
    assert "недоступен" in out
