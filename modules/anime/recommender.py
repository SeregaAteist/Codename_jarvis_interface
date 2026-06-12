"""Recommender (A-9): рекомендации по жанрам вотч-листа.

Топ-жанры из completed+watching → тайтлы каталога с этими жанрами,
которых нет в watchlist → сортировка по рейтингу Animevost.
"""
from __future__ import annotations

import json
import logging
from collections import Counter

from modules.anime import db

logger = logging.getLogger(__name__)


def _genres(raw) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [g.strip().lower() for g in data if g and g.strip()]
    except (json.JSONDecodeError, TypeError):
        return []


def top_genres(limit: int = 5) -> list[str]:
    """Самые частые жанры тайтлов в completed + watching."""
    with db.connect() as c:
        rows = c.execute(
            "SELECT t.genres FROM watchlist w JOIN titles t ON t.id = w.title_id "
            "WHERE w.status IN ('completed', 'watching')"
        ).fetchall()
    counter: Counter = Counter()
    for r in rows:
        counter.update(_genres(r["genres"]))
    return [g for g, _ in counter.most_common(limit)]


def get_recommendations(limit: int = 5) -> list[dict]:
    """Тайтлы с похожими жанрами вне вотч-листа, по rating desc."""
    genres = top_genres()
    if not genres:
        return []
    with db.connect() as c:
        candidates = c.execute(
            "SELECT t.* FROM titles t "
            "WHERE t.id NOT IN (SELECT title_id FROM watchlist) "
            "AND t.genres IS NOT NULL "
            "ORDER BY t.rating_animevost DESC NULLS LAST LIMIT 200"
        ).fetchall()

    scored: list[tuple[int, dict]] = []
    want = set(genres)
    for r in candidates:
        overlap = len(want & set(_genres(r["genres"])))
        if overlap:
            scored.append((overlap, dict(r)))
    scored.sort(key=lambda x: (-x[0], -(x[1].get("rating_animevost") or 0)))
    return [d for _, d in scored[:limit]]
