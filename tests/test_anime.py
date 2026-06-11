"""Smoke anime-модуля: init_db, rss-парсер, dispatcher (api, мок)."""
import asyncio


def test_init_db(tmp_path, monkeypatch):
    import modules.anime.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "anime.db")
    db.init_db()
    with db.connect() as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"titles", "episodes", "watchlist", "shikimori_sync"} <= tables


def test_rss_parse_atom():
    from core.parsers.rss import parse_atom
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Ep 1</title><link href="https://x/1"/><published>2030-01-01T00:00:00+00:00</published></entry>
    </feed>"""
    posts = parse_atom(xml, "src", limit=5, hours=None)
    assert len(posts) == 1 and posts[0]["title"] == "Ep 1" and posts[0]["source"] == "src"


def test_dispatcher_api_mock(monkeypatch):
    import core.parsers.dispatcher as D
    from core.parsers import api

    async def fake_fetch(self, url, params=None):
        return {"state": "ok", "data": [{"id": 1, "title": "Test Anime", "series": "{'1 серия':'u'}"}]}
    monkeypatch.setattr(api.ApiParser, "fetch", fake_fetch)

    disp = D.ParserDispatcher.__new__(D.ParserDispatcher)
    disp.sources = {"animevost": {"api_url": "https://api.x/v1", "endpoints": {"last": "/last"},
                                  "parser": "api", "limit": 3, "timeout": 5}}
    items = asyncio.run(disp.run("animevost"))
    assert len(items) == 1 and items[0]["title"] == "Test Anime"


def test_dispatcher_unknown_source():
    import core.parsers.dispatcher as D
    disp = D.ParserDispatcher.__new__(D.ParserDispatcher)
    disp.sources = {}
    assert asyncio.run(disp.run("nope")) == []
