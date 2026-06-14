"""SQLite storage for media analyzer — queue, history, deferred items."""

from __future__ import annotations

import sqlite3
import time

import config


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(config.DB_PATH)


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT,
                title TEXT,
                quick_analysis TEXT,
                deep_analysis TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deferred (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                analysis TEXT,
                media_path TEXT,
                created_at TEXT
            )
        """)


def save_item(batch_id: str, title: str, quick_analysis: str) -> int:
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO items (batch_id, title, quick_analysis, status, created_at, updated_at) VALUES (?,?,?,'pending',?,?)",
            (batch_id, title, quick_analysis, now, now),
        )
        return cur.lastrowid


def update_item(item_id: int, status: str, deep_analysis: str | None = None):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        if deep_analysis:
            conn.execute(
                "UPDATE items SET status=?, deep_analysis=?, updated_at=? WHERE id=?",
                (status, deep_analysis, now, item_id),
            )
        else:
            conn.execute(
                "UPDATE items SET status=?, updated_at=? WHERE id=?",
                (status, now, item_id),
            )


def save_deferred(title: str, analysis: str, media_path: str | None = None):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO deferred (title, analysis, media_path, created_at) VALUES (?,?,?,?)",
            (title, analysis, media_path, now),
        )


def get_deferred() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, title, analysis, media_path, created_at FROM deferred ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "analysis": r[2],
            "media_path": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]
