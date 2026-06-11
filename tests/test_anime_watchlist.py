"""A-5: watchlist CRUD — add → get → update_status → update_score → get_by_status."""
import pytest


def _fresh_db(tmp_path, monkeypatch):
    import modules.anime.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "anime.db")
    db.init_db()
    return db


def _add_title(db, title_ru: str, title_en: str = "") -> int:
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO titles (title_ru, title_en, episodes_total) VALUES (?,?,12)",
            (title_ru, title_en),
        )
        return cur.lastrowid


def test_watchlist_crud(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    from modules.anime import watchlist as wl

    tid = _add_title(db, "Атака титанов", "Attack on Titan")

    # add → get
    wid = wl.add(tid, status="planned")
    row = wl.get(wid)
    assert row["title_id"] == tid and row["status"] == "planned"

    # повторный add того же тайтла — не дублирует
    assert wl.add(tid) == wid

    # update_status
    wl.update_status(wid, "watching")
    assert wl.get(wid)["status"] == "watching"

    # update_score
    wl.update_score(wid, 9)
    assert wl.get(wid)["score"] == 9

    # get_by_status (с join тайтла)
    watching = wl.get_by_status("watching")
    assert len(watching) == 1 and watching[0]["title_ru"] == "Атака титанов"
    assert wl.get_by_status("completed") == []


def test_watchlist_validation(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    from modules.anime import watchlist as wl

    tid = _add_title(db, "Тест")
    wid = wl.add(tid)

    with pytest.raises(ValueError):
        wl.add(tid + 100, status="bad_status")
    with pytest.raises(ValueError):
        wl.update_status(wid, "unknown")
    with pytest.raises(ValueError):
        wl.update_score(wid, 11)


def test_watchlist_all_search_progress_remove(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    from modules.anime import watchlist as wl

    t1 = _add_title(db, "Атака титанов", "Attack on Titan")
    t2 = _add_title(db, "Ван Пис", "One Piece")
    w1 = wl.add(t1, status="watching")
    w2 = wl.add(t2, status="planned")

    assert len(wl.get_all()) == 2
    assert wl.get_by_title(t2)["id"] == w2

    # search по ru и en
    assert wl.search_title("титанов")[0]["id"] == w1
    assert wl.search_title("One Piece")[0]["id"] == w2
    assert wl.search_title("Наруто") == []

    wl.update_progress(w1, 5)
    assert wl.get(w1)["episodes_watched"] == 5

    wl.remove(w2)
    assert wl.get(w2) is None and len(wl.get_all()) == 1
