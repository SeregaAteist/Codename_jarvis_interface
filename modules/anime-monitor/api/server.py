from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict
from typing import Annotated

from agents.db_agent import (
    add_to_watchlist,
    get_all_snapshot,
    get_last_scan,
    get_recent_episodes,
    get_watchlist,
    update_watchlist_status,
)
from agents.recommend_agent import get_recommendations
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="J.A.R.V.I.S. Anime API")

# CORS: localhost only — no wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "null",  # Electron / local file://
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Anime-Token"],
)

# ── Auth token ────────────────────────────────────────────────────────────────

_API_TOKEN: str = os.environ.get("ANIME_API_TOKEN", "")
if not _API_TOKEN:
    _API_TOKEN = secrets.token_urlsafe(32)

# ── Rate limiting ─────────────────────────────────────────────────────────────

_rl_lock = threading.Lock()
_rl_windows: dict[str, list[float]] = defaultdict(list)
_RL_WINDOW = 60.0
_RL_LIMITS: dict[str, int] = {
    "/api/recommend": 5,
    "default": 60,
}


def _rate_ok(ip: str, path: str) -> bool:
    key = f"{ip}:{path}"
    limit = _RL_LIMITS.get(path, _RL_LIMITS["default"])
    now = time.monotonic()
    with _rl_lock:
        wins = _rl_windows[key]
        wins[:] = [t for t in wins if now - t < _RL_WINDOW]
        if len(wins) >= limit:
            return False
        wins.append(now)
        return True


def _check_request(request: Request) -> None:
    """Validate token + rate limit. Raises HTTPException on failure."""
    # Auth
    token = request.headers.get("X-Anime-Token", "")
    if not token or not secrets.compare_digest(token, _API_TOKEN):
        raise HTTPException(status_code=401, detail="unauthorized")
    # Rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_ok(client_ip, request.url.path):
        raise HTTPException(status_code=429, detail="rate limit exceeded")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "online", "agent": "J.A.R.V.I.S."}


@app.get("/anime/status")
async def anime_status(request: Request):
    """Виджет JARVIS HUD (A-11). Только агрегаты — без токена (bind 127.0.0.1)."""
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_ok(client_ip, request.url.path):
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    watchlist = get_watchlist()
    snapshot = get_all_snapshot()
    return {
        "watchlist_count": len(watchlist),
        "catalog_count": len(snapshot),
        "watching": [
            {"title": w["title"], "url": w.get("url", "")}
            for w in watchlist
            if w.get("status") == "watching"
        ],
        "last_scan": get_last_scan(),
    }


@app.get("/api/watchlist")
async def api_watchlist(request: Request):
    _check_request(request)
    return {"data": get_watchlist()}


@app.get("/api/catalog")
async def api_catalog(request: Request):
    _check_request(request)
    return {"data": get_all_snapshot()}


@app.get("/api/episodes")
async def api_episodes(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 30,
):
    _check_request(request)
    return {"data": get_recent_episodes(limit)}


@app.post("/api/watchlist/add")
async def api_add(request: Request, title: str, url: str = ""):
    _check_request(request)
    added = add_to_watchlist(title, url)
    return {"success": added}


@app.post("/api/watchlist/update")
async def api_update(request: Request, title: str, status: str):
    _check_request(request)
    ok = update_watchlist_status(title, status)
    return {"success": ok}


@app.get("/api/recommend")
async def api_recommend(request: Request):
    _check_request(request)
    result = await get_recommendations()
    return {"text": result}


from config import MODULE_DIR  # noqa: E402

app.mount(
    "/",
    StaticFiles(directory=os.path.join(MODULE_DIR, "bot", "mini_app"), html=True),
    name="mini_app",
)
