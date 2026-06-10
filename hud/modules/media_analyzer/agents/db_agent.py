"""SQLite persistence for deferred analysis pool."""

import sqlite3
from datetime import datetime

import config


def init_db() -> None:
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deferred_pool (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL,
                analysis   TEXT    NOT NULL,
                media_path TEXT,
                created_at TEXT    NOT NULL
            )
        """)
        conn.commit()


def save_deferred(title: str, analysis: str, media_path: str | None = None) -> int:
    with sqlite3.connect(config.DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO deferred_pool (title, analysis, media_path, created_at) VALUES (?, ?, ?, ?)",
            (title, analysis, media_path, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def get_deferred_list() -> list[dict]:
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM deferred_pool ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_deferred(item_id: int) -> None:
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("DELETE FROM deferred_pool WHERE id = ?", (item_id,))
        conn.commit()
