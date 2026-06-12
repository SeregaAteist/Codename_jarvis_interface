"""Shikimori sync (A-10) — активен только при SHIKIMORI_TOKEN в .env.

API: https://shikimori.one/api (OAuth2 Bearer). Синхронизация вотч-листа:
локальные записи → user_rates Shikimori (по shikimori_id тайтла).
"""
from __future__ import annotations

import logging
import os

from modules.anime import db

logger = logging.getLogger(__name__)

_API = "https://shikimori.one/api"
_STATUS_MAP = {  # локальный → shikimori
    "watching": "watching", "completed": "completed", "planned": "planned",
    "dropped": "dropped", "on_hold": "on_hold",
}


def is_available() -> bool:
    return bool(os.getenv("SHIKIMORI_TOKEN", "").strip())


async def _me(cli) -> dict:
    r = await cli.get(f"{_API}/users/whoami")
    r.raise_for_status()
    return r.json()


async def sync_watchlist() -> dict:
    """Локальный watchlist → Shikimori user_rates. Возвращает {added, updated}."""
    if not is_available():
        raise RuntimeError("SHIKIMORI_TOKEN не задан в .env")
    import httpx

    token = os.getenv("SHIKIMORI_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}",
               "User-Agent": "jarvis-anime-monitor"}

    with db.connect() as c:
        rows = c.execute(
            "SELECT w.status, w.score, w.episodes_watched, t.shikimori_id "
            "FROM watchlist w JOIN titles t ON t.id = w.title_id "
            "WHERE t.shikimori_id IS NOT NULL"
        ).fetchall()

    added = updated = 0
    async with httpx.AsyncClient(timeout=30, headers=headers) as cli:
        me = await _me(cli)
        user_id = me["id"]
        for r in rows:
            body = {"user_rate": {
                "user_id": user_id,
                "target_id": r["shikimori_id"],
                "target_type": "Anime",
                "status": _STATUS_MAP.get(r["status"], "planned"),
                "episodes": r["episodes_watched"] or 0,
            }}
            if r["score"]:
                body["user_rate"]["score"] = r["score"]
            resp = await cli.post(f"{_API}/v2/user_rates", json=body)
            if resp.status_code == 201:
                added += 1
            elif resp.status_code in (200, 422):  # 422 — уже существует
                updated += 1

    with db.connect() as c:
        c.execute("INSERT INTO shikimori_sync (titles_added, titles_updated) VALUES (?,?)",
                  (added, updated))
    return {"added": added, "updated": updated}
