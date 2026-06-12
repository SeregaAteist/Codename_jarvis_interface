"""Matcher (A-6): новые серии для тайтлов в watching.

Animevost отдаёт тайтл с полем series — строка-словарь «{'1 серия': 'url', ...}».
Сравниваем номер последней вышедшей серии с тем, что уже в episodes.
"""
from __future__ import annotations

import ast
import logging
import re
import time

from modules.anime import db

logger = logging.getLogger(__name__)

_NUM = re.compile(r"(\d+)")


def parse_series(raw) -> dict[int, str]:
    """series от Animevost → {номер: url}. Терпимо к мусору."""
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[int, str] = {}
    for name, url in raw.items():
        m = _NUM.search(str(name))
        if m:
            out[int(m.group(1))] = url if isinstance(url, str) else ""
    return out


def find_new_episodes(parsed_titles: list[dict]) -> list[dict]:
    """Новые серии ТОЛЬКО для тайтлов со статусом watching в watchlist.

    Возвращает [{title_id, title_ru, title_en, season, episode_number,
                 episode_name, url, score}].
    """
    with db.connect() as c:
        watching = c.execute(
            "SELECT w.title_id, w.score, t.animevost_id, t.title_ru, t.title_en "
            "FROM watchlist w JOIN titles t ON t.id = w.title_id "
            "WHERE w.status='watching' AND t.animevost_id IS NOT NULL"
        ).fetchall()
        if not watching:
            return []
        by_avid = {r["animevost_id"]: dict(r) for r in watching}

        known: dict[int, set[int]] = {}
        for r in c.execute(
            "SELECT title_id, episode_number FROM episodes WHERE title_id IN "
            f"({','.join(str(w['title_id']) for w in by_avid.values())})"
        ):
            known.setdefault(r["title_id"], set()).add(r["episode_number"])

    new: list[dict] = []
    for t in parsed_titles:
        avid = t.get("id")
        w = by_avid.get(avid)
        if not w:
            continue
        for ep_num, url in sorted(parse_series(t.get("series")).items()):
            if ep_num in known.get(w["title_id"], set()):
                continue
            new.append({
                "title_id": w["title_id"],
                "title_ru": w["title_ru"],
                "title_en": w["title_en"],
                "season": 1,
                "episode_number": ep_num,
                "episode_name": f"Серия {ep_num}",
                "url": url or t.get("url", ""),
                "score": w["score"],
            })
    return new


def save_episodes(episodes: list[dict]) -> list[int]:
    """Сохранить новые серии. Возвращает id вставленных записей."""
    ids: list[int] = []
    with db.connect() as c:
        for e in episodes:
            cur = c.execute(
                "INSERT INTO episodes (title_id, season, episode_number, episode_name, url) "
                "VALUES (?,?,?,?,?)",
                (e["title_id"], e.get("season", 1), e["episode_number"],
                 e.get("episode_name", ""), e.get("url", "")),
            )
            ids.append(cur.lastrowid)
    return ids


def mark_notified(episode_ids: list[int]) -> None:
    if not episode_ids:
        return
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with db.connect() as c:
        c.executemany(
            "UPDATE episodes SET notified_at=? WHERE id=?",
            [(now, eid) for eid in episode_ids],
        )
