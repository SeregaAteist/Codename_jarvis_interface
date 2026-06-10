"""MCP server — Anime Catalog (jarvis_animevost SQLite backend)."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path.home() / "Downloads" / "jarvis_animevost" / "data" / "anime.db"

mcp = FastMCP("anime-catalog")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@mcp.tool()
def search_anime(query: str) -> list[dict]:
    """Search anime by title. Multi-word queries require all words to match (AND logic).
    Works with mixed Russian/Japanese/English titles. Returns up to 20 matches by MAL score."""
    words = [w for w in query.strip().split() if w]
    if not words:
        return []

    conditions = " AND ".join("title LIKE ?" for _ in words)
    params = [f"%{w}%" for w in words]

    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT id, title, episode, rating, genres, year, mal_score, synopsis
            FROM anime_snapshot
            WHERE {conditions}
            ORDER BY mal_score DESC NULLS LAST
            LIMIT 20
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def get_watchlist() -> list[dict]:
    """Return all entries in the watchlist."""
    with _conn() as con:
        rows = con.execute(
            "SELECT id, title, url, status, added_at FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def add_to_watchlist(anime_id: int) -> dict:
    """Add an anime (by anime_snapshot.id) to the watchlist. Status defaults to 'watching'."""
    with _conn() as con:
        anime = con.execute(
            "SELECT id, title, url FROM anime_snapshot WHERE id = ?", (anime_id,)
        ).fetchone()
        if not anime:
            return {"error": f"Anime id={anime_id} not found in catalog"}

        existing = con.execute(
            "SELECT id, status, added_at FROM watchlist WHERE url = ? AND url != ''",
            (anime["url"],),
        ).fetchone()
        if not existing and anime["url"] == "":
            existing = con.execute(
                "SELECT id, status, added_at FROM watchlist WHERE title = ?",
                (anime["title"],),
            ).fetchone()
        if existing:
            return {
                "watchlist_id": existing["id"],
                "title": anime["title"],
                "status": existing["status"],
                "added_at": existing["added_at"],
                "duplicate": True,
            }

        now = datetime.now(timezone.utc).isoformat()
        cur = con.execute(
            "INSERT INTO watchlist (title, url, status, added_at) VALUES (?, ?, 'watching', ?)",
            (anime["title"], anime["url"], now),
        )
        con.commit()
        return {
            "watchlist_id": cur.lastrowid,
            "title": anime["title"],
            "status": "watching",
            "added_at": now,
            "duplicate": False,
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
