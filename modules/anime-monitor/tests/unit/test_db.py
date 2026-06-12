"""SQLite: upsert, watchlist, статусы (A-8), миграция."""
from agents import db_agent as db


def test_upsert_new_and_episode(tmp_db, sample_items):
    new = db.upsert_anime(sample_items)
    assert len(new) == 2 and all(i["reason"] == "new_anime" for i in new)

    # без изменений — пусто
    assert db.upsert_anime(sample_items) == []

    # новая серия
    sample_items[1]["episode"] = "6 из 24"
    new = db.upsert_anime(sample_items)
    assert len(new) == 1 and new[0]["reason"] == "new_episode"


def test_watchlist_status_default(tmp_db):
    assert db.add_to_watchlist("Тест", "https://x/1") is True
    row = db.get_watchlist()[0]
    assert row["status"] == "watching"   # дефолт A-8

    # повторное добавление → не дублирует, возвращает в watching
    assert db.add_to_watchlist("Тест") is False
    assert len(db.get_watchlist()) == 1


def test_status_update_and_filter(tmp_db):
    db.add_to_watchlist("А")
    db.add_to_watchlist("Б")
    wid = db.get_watchlist()[0]["id"]

    assert db.update_status_by_id(wid, "completed") is True
    assert db.update_status_by_id(wid, "не_статус") is False
    assert db.update_watchlist_status("Б", "dropped") is True

    assert {w["status"] for w in db.get_watchlist()} == {"completed", "dropped"}
    assert len(db.get_watchlist(status="completed")) == 1
    assert db.get_watchlist(status="watching") == []


def test_migration_adds_status_column(tmp_path, monkeypatch):
    """Старая БД без watchlist.status → init_db мигрирует."""
    import sqlite3
    from config import cfg

    db_path = str(tmp_path / "old.db")
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    c = sqlite3.connect(db_path)
    c.execute("CREATE TABLE watchlist (id INTEGER PRIMARY KEY, title TEXT, url TEXT, added_at TEXT)")
    c.commit()
    c.close()

    db.init_db()
    db.add_to_watchlist("Старый")
    assert db.get_watchlist()[0]["status"] == "watching"
