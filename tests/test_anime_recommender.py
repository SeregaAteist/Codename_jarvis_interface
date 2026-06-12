"""A-9/A-10: recommender — топ-жанры, рекомендации вне вотч-листа; shikimori gate."""
import json


def _fresh_db(tmp_path, monkeypatch):
    import modules.anime.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "anime.db")
    db.init_db()
    return db


def _title(db, name, genres, rating=7.0, wl=None):
    with db.connect() as c:
        tid = c.execute(
            "INSERT INTO titles (title_ru, genres, rating_animevost) VALUES (?,?,?)",
            (name, json.dumps(genres, ensure_ascii=False), rating),
        ).lastrowid
        if wl:
            c.execute("INSERT INTO watchlist (title_id, status) VALUES (?,?)", (tid, wl))
    return tid


def test_top_genres(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    from modules.anime.recommender import top_genres

    _title(db, "A", ["фэнтези", "приключения"], wl="completed")
    _title(db, "B", ["фэнтези", "драма"], wl="watching")
    _title(db, "C", ["меха"], wl="planned")        # planned не учитывается

    top = top_genres()
    assert top[0] == "фэнтези"
    assert "меха" not in top


def test_recommendations_exclude_watchlist(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    from modules.anime.recommender import get_recommendations

    _title(db, "Смотрю", ["фэнтези"], wl="watching")
    _title(db, "Кандидат высокий", ["фэнтези", "приключения"], rating=9.1)
    _title(db, "Кандидат низкий", ["фэнтези"], rating=5.0)
    _title(db, "Мимо жанра", ["спорт"], rating=9.9)

    recs = get_recommendations(limit=5)
    names = [r["title_ru"] for r in recs]
    assert "Кандидат высокий" in names and "Кандидат низкий" in names
    assert "Смотрю" not in names and "Мимо жанра" not in names
    assert names[0] == "Кандидат высокий"  # больший overlap+рейтинг выше


def test_recommendations_empty_without_history(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.anime.recommender import get_recommendations
    assert get_recommendations() == []


def test_shikimori_gate(monkeypatch):
    from modules.anime import shikimori

    monkeypatch.delenv("SHIKIMORI_TOKEN", raising=False)
    assert not shikimori.is_available()
    monkeypatch.setenv("SHIKIMORI_TOKEN", "tok")
    assert shikimori.is_available()
