"""Anime БД (SQLite, отдельно от jarvis.db). Инициализация из schema.sql."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.config import CFG

DB_PATH = CFG.DATA_DIR / "sqlite" / "anime.db"
_SCHEMA = Path(__file__).parent / "schema.sql"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as c:
        c.executescript(_SCHEMA.read_text(encoding="utf-8"))
