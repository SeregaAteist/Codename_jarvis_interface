import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional
from config import cfg


@contextmanager
def conn():
    c = sqlite3.connect(cfg.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS anime_snapshot (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            episode     TEXT,
            rating      TEXT,
            genres      TEXT,
            year        TEXT,
            img_url     TEXT,
            mal_score   REAL,
            mal_id      INTEGER,
            synopsis    TEXT,
            first_seen  TEXT NOT NULL,
            last_seen   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            url         TEXT DEFAULT '',
            status      TEXT DEFAULT 'watching',
            added_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS episodes_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_url   TEXT NOT NULL,
            anime_title TEXT NOT NULL,
            episode     TEXT,
            detected_at TEXT NOT NULL,
            notified    INTEGER DEFAULT 0
        );
        """)
    print("[БД] Инициализация завершена.")


def upsert_anime(items: list[dict]) -> list[dict]:
    now = datetime.now().isoformat(timespec="seconds")
    new_items = []
    with conn() as c:
        for item in items:
            existing = c.execute(
                "SELECT episode FROM anime_snapshot WHERE url = ?",
                (item["url"],)
            ).fetchone()
            if existing is None:
                c.execute("""
                    INSERT INTO anime_snapshot
                        (url,title,episode,rating,genres,year,img_url,
                         mal_score,mal_id,synopsis,first_seen,last_seen)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    item["url"], item["title"], item.get("episode"),
                    item.get("rating"), item.get("genres"), item.get("year"),
                    item.get("img_url"), item.get("mal_score"),
                    item.get("mal_id"), item.get("synopsis"), now, now
                ))
                new_items.append({**item, "reason": "new_anime"})
            elif existing["episode"] != item.get("episode"):
                c.execute("""
                    UPDATE anime_snapshot
                    SET episode=?, last_seen=?
                    WHERE url=?
                """, (item.get("episode"), now, item["url"]))
                new_items.append({**item, "reason": "new_episode"})
            else:
                c.execute(
                    "UPDATE anime_snapshot SET last_seen=? WHERE url=?",
                    (now, item["url"])
                )
    return new_items


def log_episodes(items: list[dict]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        for item in items:
            c.execute("""
                INSERT INTO episodes_log
                    (anime_url, anime_title, episode, detected_at)
                VALUES (?,?,?,?)
            """, (item["url"], item["title"], item.get("episode"), now))


def get_watchlist() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM watchlist WHERE status='watching' ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def add_to_watchlist(title: str, url: str = "") -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        existing = c.execute(
            "SELECT id FROM watchlist WHERE title=? AND status='watching'", (title,)
        ).fetchone()
        if existing:
            return False
        c.execute("""
            INSERT INTO watchlist (title, url, status, added_at)
            VALUES (?,?,?,?)
        """, (title, url, "watching", now))
    return True


def update_watchlist_status(title: str, status: str) -> bool:
    with conn() as c:
        cur = c.execute(
            "UPDATE watchlist SET status=? WHERE title=? AND status='watching'",
            (status, title)
        )
        return cur.rowcount > 0


def get_recent_episodes(limit: int = 20) -> list[dict]:
    with conn() as c:
        rows = c.execute("""
            SELECT * FROM episodes_log
            ORDER BY detected_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_all_snapshot() -> list[dict]:
    with conn() as c:
        rows = c.execute("""
            SELECT title, url, genres, rating, mal_score, img_url, episode
            FROM anime_snapshot
            ORDER BY last_seen DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_unnotified_episodes() -> list[dict]:
    with conn() as c:
        rows = c.execute("""
            SELECT * FROM episodes_log WHERE notified=0
            ORDER BY detected_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def mark_notified(episode_ids: list[int]) -> None:
    with conn() as c:
        c.executemany(
            "UPDATE episodes_log SET notified=1 WHERE id=?",
            [(i,) for i in episode_ids]
        )
