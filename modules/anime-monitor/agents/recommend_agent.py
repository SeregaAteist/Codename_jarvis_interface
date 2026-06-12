"""Рекомендации через общий LLM-роутер JARVIS (роль 'recommend' → Gemini).

Прямых HTTP-вызовов LLM здесь нет: провайдер/модель/retry/ключи — забота
shared/llm/router. Fallback и ротация ключей — внутри роутера.
"""
import logging
import os
import sys

from agents.db_agent import get_watchlist, get_all_snapshot

logger = logging.getLogger("recommend")

JARVIS_ROOT = os.path.expanduser("~/Projects/jarvis")
if JARVIS_ROOT not in sys.path:
    sys.path.insert(0, JARVIS_ROOT)


async def _llm_generate(prompt: str) -> str:
    """Тонкая обёртка над router.generate — единственная точка мока в тестах."""
    from shared.llm import router
    return await router.generate("recommend", prompt)


def build_prompt(watchlist: list[dict], catalog: list[dict]) -> str:
    watching_titles = [w["title"] for w in watchlist]
    catalog_titles = [
        f"{a['title']} (жанры: {a.get('genres','?')}, "
        f"рейтинг MAL: {a.get('mal_score','?')})"
        for a in catalog[:80]
    ]
    return f"""Ты — аниме-эксперт. Пользователь смотрит:
{chr(10).join(f'- {t}' for t in watching_titles)}

Из каталога доступны:
{chr(10).join(f'- {t}' for t in catalog_titles)}

Порекомендуй 5 аниме из каталога, которые понравятся этому пользователю.
Для каждого напиши: название, почему подойдёт (1-2 предложения).
Отвечай на русском языке, кратко и по делу."""


async def get_recommendations() -> str:
    watchlist = get_watchlist(status="watching")
    catalog = get_all_snapshot()

    if not watchlist:
        return (
            "Сэр, ваш список просмотров пуст. "
            "Добавьте несколько тайтлов через кнопку «Добавить», "
            "и я подберу достойные рекомендации."
        )

    try:
        return await _llm_generate(build_prompt(watchlist, catalog))
    except Exception as e:
        logger.error("LLM-роутер недоступен: %s", e)
        return (
            "Сэр, рекомендательный модуль временно недоступен "
            f"({type(e).__name__}). Попробуйте позже."
        )
