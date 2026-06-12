"""A-6/A-7: matcher — parse_series, новые серии только для watching; уведомление."""
import asyncio


def _fresh_db(tmp_path, monkeypatch):
    import modules.anime.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "anime.db")
    db.init_db()
    return db


def _seed_title(db, avid: int, title: str, wl_status: str | None, score=None) -> int:
    with db.connect() as c:
        tid = c.execute(
            "INSERT INTO titles (animevost_id, title_ru, title_en) VALUES (?,?,?)",
            (avid, title, title + " EN"),
        ).lastrowid
        if wl_status:
            c.execute(
                "INSERT INTO watchlist (title_id, status, score) VALUES (?,?,?)",
                (tid, wl_status, score),
            )
    return tid


def test_parse_series():
    from modules.anime.matcher import parse_series

    assert parse_series("{'1 серия': 'u1', '2 серия': 'u2'}") == {1: "u1", 2: "u2"}
    assert parse_series(None) == {}
    assert parse_series("мусор {") == {}
    assert parse_series({"Серия 3": "u"}) == {3: "u"}


def test_find_new_episodes_only_watching(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    from modules.anime import matcher

    t_watch = _seed_title(db, 100, "Атака титанов", "watching", score=9)
    _seed_title(db, 200, "Ван Пис", "planned")          # planned — не уведомляем
    _seed_title(db, 300, "Наруто", None)                  # вне вотч-листа

    # серия 1 уже в БД
    with db.connect() as c:
        c.execute("INSERT INTO episodes (title_id, episode_number) VALUES (?, 1)", (t_watch,))

    parsed = [
        {"id": 100, "series": "{'1 серия': 'u1', '2 серия': 'u2'}"},
        {"id": 200, "series": "{'5 серия': 'u5'}"},
        {"id": 999, "series": "{'1 серия': 'x'}"},        # неизвестный тайтл
    ]
    new = matcher.find_new_episodes(parsed)
    assert len(new) == 1
    ep = new[0]
    assert ep["episode_number"] == 2 and ep["title_ru"] == "Атака титанов" and ep["score"] == 9

    # save + mark_notified
    ids = matcher.save_episodes(new)
    assert len(ids) == 1
    matcher.mark_notified(ids)
    with db.connect() as c:
        row = c.execute("SELECT notified_at FROM episodes WHERE id=?", (ids[0],)).fetchone()
    assert row["notified_at"] is not None

    # повторный прогон — серия уже в БД, новых нет
    assert matcher.find_new_episodes(parsed) == []


def test_episode_notification_format():
    from agents.anime import format_episode_notification

    text = format_episode_notification({
        "title_ru": "Атака титанов", "title_en": "Attack on Titan",
        "season": 1, "episode_number": 2, "episode_name": "Серия 2", "score": 9,
    })
    assert "🎬 Новая серия!" in text
    assert "Атака титанов (Attack on Titan)" in text
    assert "Сезон 1, серия 2" in text
    assert "⭐️ Ваша оценка: 9/10" in text


def test_agent_check_no_animevost(monkeypatch):
    from agents.anime import AnimeAgent
    from core.parsers.dispatcher import ParserDispatcher

    async def fake_run(self, name):
        return []
    monkeypatch.setattr(ParserDispatcher, "run", fake_run)
    out = asyncio.run(AnimeAgent().check_new_episodes())
    assert "пропущена" in out
