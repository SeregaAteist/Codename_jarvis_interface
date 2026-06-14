"""Управление rafail.db: materials, processed, moodle_map, sync_log.

CRUD-слой для модуля Рафаил (корпоративная БЗ LK Energy Group).
Все функции синхронные (sqlite3), вызываются из async-кода через
обычный вызов — операции короткие, блокировка незаметна.
"""

from __future__ import annotations

import time

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


def get_material(material_id: int) -> dict | None:
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
    material_id: int | None,
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


def get_processed(processed_id: int) -> dict | None:
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM processed WHERE id=?", (processed_id,)
        ).fetchone()
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
            (
                processed_id,
                moodle_course_id,
                moodle_section_id,
                moodle_activity_id,
                drive_file_id,
            ),
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


# ── конфигурация в БД (RF-12): sources / prompts / drive_folders / settings ──


def get_sources(domain: str = "", enabled_only: bool = True) -> list[dict]:
    q = "SELECT * FROM sources WHERE 1=1"
    params: list = []
    if enabled_only:
        q += " AND enabled=1"
    if domain:
        q += " AND domain=?"
        params.append(domain)
    with db.connect() as c:
        rows = c.execute(q + " ORDER BY domain, name", params).fetchall()
    return [dict(r) for r in rows]


def add_source(
    domain: str,
    name: str,
    url: str,
    type_: str = "rss",
    selector: str = "",
    track: str = "all",
) -> int:
    with db.connect() as c:
        cur = c.execute(
            "INSERT INTO sources (domain,name,url,type,selector,track) VALUES (?,?,?,?,?,?)",
            (domain, name, url, type_, selector or None, track),
        )
        return cur.lastrowid


def delete_source(source_id: int) -> None:
    with db.connect() as c:
        c.execute("DELETE FROM sources WHERE id=?", (source_id,))


def toggle_source(source_id: int, enabled: bool) -> None:
    with db.connect() as c:
        c.execute(
            "UPDATE sources SET enabled=? WHERE id=?", (1 if enabled else 0, source_id)
        )


def get_prompt(name: str) -> str:
    with db.connect() as c:
        row = c.execute("SELECT content FROM prompts WHERE name=?", (name,)).fetchone()
    if not row:
        raise KeyError(f"Промпт '{name}' не найден в БД")
    return row["content"]


def set_prompt(name: str, content: str) -> None:
    with db.connect() as c:
        c.execute(
            "INSERT INTO prompts (name,content,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET content=?, updated_at=?",
            (name, content, _now(), content, _now()),
        )


def list_prompts() -> list[str]:
    with db.connect() as c:
        return [r["name"] for r in c.execute("SELECT name FROM prompts ORDER BY name")]


def get_folders() -> dict[str, str]:
    """{key: folder_id} — Drive-папки из БД."""
    with db.connect() as c:
        return {
            r["key"]: r["folder_id"]
            for r in c.execute("SELECT key, folder_id FROM drive_folders")
        }


def get_folders_full() -> list[dict]:
    with db.connect() as c:
        rows = c.execute("SELECT * FROM drive_folders ORDER BY key").fetchall()
    return [dict(r) for r in rows]


def add_folder(key: str, folder_id: str, title: str = "") -> None:
    with db.connect() as c:
        c.execute(
            "INSERT INTO drive_folders (key,folder_id,title) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET folder_id=excluded.folder_id, title=excluded.title",
            (key, folder_id, title),
        )


def delete_folder(key: str) -> None:
    with db.connect() as c:
        c.execute("DELETE FROM drive_folders WHERE key=?", (key,))


def get_setting(key: str, default: str = "") -> str:
    with db.connect() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db.connect() as c:
        c.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ── stats ─────────────────────────────────────────────────────────────────────


def get_stats() -> dict:
    """Сводка для /rafail status."""
    with db.connect() as c:
        materials = c.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
        by_status = dict(
            c.execute(
                "SELECT status, COUNT(*) FROM processed GROUP BY status"
            ).fetchall()
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
