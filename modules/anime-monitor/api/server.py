from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from agents.db_agent import (
    get_watchlist, get_all_snapshot,
    get_recent_episodes, add_to_watchlist, update_watchlist_status
)
from agents.recommend_agent import get_recommendations

app = FastAPI(title="J.A.R.V.I.S. Anime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/watchlist")
async def api_watchlist():
    return {"data": get_watchlist()}


@app.get("/api/catalog")
async def api_catalog():
    return {"data": get_all_snapshot()}


@app.get("/api/episodes")
async def api_episodes(limit: int = 30):
    return {"data": get_recent_episodes(limit)}


@app.post("/api/watchlist/add")
async def api_add(title: str, url: str = ""):
    added = add_to_watchlist(title, url)
    return {"success": added}


@app.post("/api/watchlist/update")
async def api_update(title: str, status: str):
    ok = update_watchlist_status(title, status)
    return {"success": ok}


@app.get("/api/recommend")
async def api_recommend():
    result = await get_recommendations()
    return {"text": result}


@app.get("/api/health")
async def health():
    return {"status": "online", "agent": "J.A.R.V.I.S."}


app.mount(
    "/",
    StaticFiles(directory="bot/mini_app", html=True),
    name="mini_app"
)
