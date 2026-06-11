"""Управление rafail.db: materials, processed, moodle_map, sync_log.

CRUD-слой для модуля Рафаил (корпоративная БЗ LK Energy Group).
Все функции синхронные (sqlite3), вызываются из async-кода через
обычный вызов — операции короткие, блокировка незаметна.
"""
from __future__ import annotations

import time
from typing import Optional

from modules.rafail import db


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ── materials ─────────────────────────────────────────────────────────────────

def add_material(
    domain: str,
    track: str,
    title: str,
    raw_content: str,
    source_url: str = "",
    source_type: str = "web",
) -> int:
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO materials (domain, track, source_url, source_type, title, raw_content) "
            "VALUES (?,?,?,?,?,?)",
            (domain, track, source_url, source_type, title, raw_content),
        )
        return cur.lastrowid


def get_material(material_id: int) -> Optional[dict]:
    with db.connect() as c:
        row = c.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    return dict(row) if row else None


def get_materials(domain: str = "", track: str = "", limit: int = 50) -> list[dict]:
    q = "SELECT * FROM materials WHERE 1=1"
    params: list = []
    if domain:
        q += " AND domain=?"
        params.append(domain)
    if track:
        q += " AND track IN (?, 'all')"
        params.append(track)
    q += " ORDER BY collected_at DESC LIMIT ?"
    params.append(limit)
    with db.connect() as c:
        rows = c.execute(q, params).fetchall()
    return [dict(r) for r in rows]


def search_materials(query: str, limit: int = 20) -> list[dict]:
    like = f"%{query}%"
    with db.connect() as c:
        rows = c.execute(
            "SELECT * FROM materials WHERE title LIKE ? OR raw_content LIKE ? "
            "ORDER BY collected_at DESC LIMIT ?",
            (like, like, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def material_exists(source_url: str) -> bool:
    """Дедупликация при сборе: материал с таким URL уже есть."""
    if not source_url:
        return False
    with db.connect() as c:
        row = c.execute(
            "SELECT 1 FROM materials WHERE source_url=? LIMIT 1", (source_url,)
        ).fetchone()
    return row is not None


# ── processed ─────────────────────────────────────────────────────────────────

def add_processed(
    material_id: Optional[int],
    content_type: str,
    track: str,
    title: str,
    content: str,
) -> int:
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO processed (material_id, content_type, track, title, content) "
            "VALUES (?,?,?,?,?)",
            (material_id, content_type, track, title, content),
        )
        return cur.lastrowid


def get_processed(processed_id: int) -> Optional[dict]:
    with db.connect() as c:
        row = c.execute("SELECT * FROM processed WHERE id=?", (processed_id,)).fetchone()
    return dict(row) if row else None


def get_pending(limit: int = 20) -> list[dict]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT * FROM processed WHERE status='pending' ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def approve(processed_id: int) -> None:
    with db.connect() as c:
        c.execute(
            "UPDATE processed SET status='approved', approved_at=? WHERE id=?",
            (_now(), processed_id),
        )


def reject(processed_id: int, reason: str = "") -> None:
    with db.connect() as c:
        c.execute(
            "UPDATE processed SET status='rejected', rejection_reason=? WHERE id=?",
            (reason, processed_id),
        )


def mark_uploaded(processed_id: int) -> None:
    with db.connect() as c:
        c.execute("UPDATE processed SET status='uploaded' WHERE id=?", (processed_id,))


def update_content(processed_id: int, content: str) -> None:
    """Применить правки владельца: новый контент, статус снова pending."""
    with db.connect() as c:
        c.execute(
            "UPDATE processed SET content=?, status='pending', rejection_reason=NULL WHERE id=?",
            (content, processed_id),
        )


# ── moodle_map ────────────────────────────────────────────────────────────────

def map_moodle(
    processed_id: int,
    moodle_course_id: int = 0,
    moodle_section_id: int = 0,
    moodle_activity_id: int = 0,
    drive_file_id: str = "",
) -> int:
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO moodle_map (processed_id, moodle_course_id, moodle_section_id, "
            "moodle_activity_id, drive_file_id) VALUES (?,?,?,?,?)",
            (processed_id, moodle_course_id, moodle_section_id, moodle_activity_id, drive_file_id),
        )
        return cur.lastrowid


def get_moodle_map(processed_id: int) -> list[dict]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT * FROM moodle_map WHERE processed_id=? ORDER BY uploaded_at DESC",
            (processed_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── sync_log ──────────────────────────────────────────────────────────────────

def log_sync(action: str, status: str, details: str = "") -> None:
    with db.connect() as c:
        c.execute(
            "INSERT INTO sync_log (action, status, details) VALUES (?,?,?)",
            (action, status, details),
        )


def get_sync_log(limit: int = 50) -> list[dict]:
    with db.connect() as c:
        rows = c.execute(
            "SELECT * FROM sync_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Сводка для /rafail status."""
    with db.connect() as c:
        materials = c.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
        by_status = dict(
            c.execute("SELECT status, COUNT(*) FROM processed GROUP BY status").fetchall()
        )
        uploaded = c.execute("SELECT COUNT(*) FROM moodle_map").fetchone()[0]
    return {
        "materials": materials,
        "pending": by_status.get("pending", 0),
        "approved": by_status.get("approved", 0),
        "rejected": by_status.get("rejected", 0),
        "uploaded": by_status.get("uploaded", 0),
        "moodle_entries": uploaded,
    }
