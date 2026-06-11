"""Вотч-лист (A-5): CRUD над таблицей watchlist + join с titles.

Статусы: watching / completed / planned / dropped / on_hold.
"""
from __future__ import annotations

import time
from typing import Optional

from modules.anime import db

STATUSES = ("watching", "completed", "planned", "dropped", "on_hold")


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"Недопустимый статус '{status}'. Допустимые: {', '.join(STATUSES)}")


def add(title_id: int, status: str = "planned", notes: str = "") -> int:
    """Добавить тайтл в вотч-лист. Если уже есть — вернуть существующий id."""
    _check_status(status)
    with db.connect() as c:
        row = c.execute(
            "SELECT id FROM watchlist WHERE title_id=?", (title_id,)
        ).fetchone()
        if row:
            return row["id"]
        cur = c.execute(
            "INSERT INTO watchlist (title_id, status, notes) VALUES (?,?,?)",
            (title_id, status, notes),
        )
        return cur.lastrowid


def get(watch_id: int) -> Optional[dict]:
    with db.connect() as c:
        row = c.execute("SELECT * FROM watchlist WHERE id=?", (watch_id,)).fetchone()
    return dict(row) if row else None


def get_by_title(title_id: int) -> Optional[dict]:
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM watchlist WHERE title_id=?", (title_id,)
        ).fetchone()
    return dict(row) if row else None


def update_status(watch_id: int, status: str) -> None:
    _check_status(status)
    with db.connect() as c:
        c.execute(
            "UPDATE watchlist SET status=?, updated_at=? WHERE id=?",
            (status, _now(), watch_id),
        )


def update_score(watch_id: int, score: int) -> None:
    if not 1 <= score <= 10:
        raise ValueError("Оценка должна быть от 1 до 10")
    with db.connect() as c:
        c.execute(
            "UPDATE watchlist SET score=?, updated_at=? WHERE id=?",
            (score, _now(), watch_id),
        )


def update_progress(watch_id: int, episodes_watched: int) -> None:
    with db.connect() as c:
        c.execute(
            "UPDATE watchlist SET episodes_watched=?, updated_at=? WHERE id=?",
            (episodes_watched, _now(), watch_id),
        )


def remove(watch_id: int) -> None:
    with db.connect() as c:
        c.execute("DELETE FROM watchlist WHERE id=?", (watch_id,))


def get_by_status(status: str) -> list[dict]:
    """Записи вотч-листа с данными тайтла (join titles)."""
    _check_status(status)
    with db.connect() as c:
        rows = c.execute(
            "SELECT w.*, t.title_ru, t.title_en, t.poster_url, t.episodes_total "
            "FROM watchlist w LEFT JOIN titles t ON t.id = w.title_id "
            "WHERE w.status=? ORDER BY w.updated_at DESC",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all() -> list[dict]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT w.*, t.title_ru, t.title_en, t.poster_url, t.episodes_total "
            "FROM watchlist w LEFT JOIN titles t ON t.id = w.title_id "
            "ORDER BY w.updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def search_title(query: str) -> list[dict]:
    """Поиск по вотч-листу по названию тайтла (ru/en/original)."""
    like = f"%{query}%"
    with db.connect() as c:
        rows = c.execute(
            "SELECT w.*, t.title_ru, t.title_en, t.poster_url, t.episodes_total "
            "FROM watchlist w JOIN titles t ON t.id = w.title_id "
            "WHERE t.title_ru LIKE ? OR t.title_en LIKE ? OR t.title_original LIKE ? "
            "ORDER BY w.updated_at DESC",
            (like, like, like),
        ).fetchall()
    return [dict(r) for r in rows]
