import httpx
import json
from agents.db_agent import get_watchlist, get_all_snapshot
from config import cfg


async def get_recommendations() -> str:
    watchlist = get_watchlist()
    catalog = get_all_snapshot()

    if not watchlist:
        return (
            "Сэр, ваш список просмотров пуст. "
            "Добавьте несколько тайтлов через кнопку «Добавить», "
            "и я подберу достойные рекомендации."
        )

    watching_titles = [w["title"] for w in watchlist]
    catalog_titles = [
        f"{a['title']} (жанры: {a.get('genres','?')}, "
        f"рейтинг MAL: {a.get('mal_score','?')})"
        for a in catalog[:80]
    ]

    prompt = f"""Ты — аниме-эксперт. Пользователь смотрит:
{chr(10).join(f'- {t}' for t in watching_titles)}

Из каталога доступны:
{chr(10).join(f'- {t}' for t in catalog_titles)}

Порекомендуй 5 аниме из каталога, которые понравятся этому пользователю.
Для каждого напиши: название, почему подойдёт (1-2 предложения).
Отвечай на русском языке, кратко и по делу."""

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{cfg.OLLAMA_URL}/api/generate",
                json={
                    "model": cfg.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 600}
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "Ollama не вернула ответ.")
    except httpx.ConnectError:
        return (
            "Сэр, Ollama недоступна. "
            "Убедитесь что запущен: `ollama serve` "
            "и установлена модель: `ollama pull llama3.2`"
        )
    except Exception as e:
        return f"Ошибка рекомендательного агента: {e}"


async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{cfg.OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
