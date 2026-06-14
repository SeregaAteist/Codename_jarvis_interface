"""
Overnight batch scraper — all genres, 2020-2026, enriched via AniList (free).
Usage: python batch_scrape.py
"""

import asyncio
import sys
import time

sys.path.insert(0, ".")

from agents.anilist_agent import enrich_with_anilist
from agents.db_agent import init_db, upsert_anime
from agents.scraper_agent import scrape_category

YEAR_MIN = 2020
YEAR_MAX = 2026

# Genres to scrape (fantasy already done)
GENRES = [
    ("Приключения", "/zhanr/priklyucheniya/"),
    ("Комедия", "/zhanr/komediya/"),
]

STATS = {"genres_done": 0, "total_raw": 0, "total_saved": 0, "errors": []}


async def process_genre(name: str, path: str) -> None:
    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"[Батч] Жанр: {name}  ({path})")
    print(f"{'='*60}")

    try:
        raw = await scrape_category(path, year_min=YEAR_MIN, year_max=YEAR_MAX)
        if not raw:
            print(f"[Батч] {name}: ничего не найдено, пропускаем.")
            return

        STATS["total_raw"] += len(raw)
        print(f"[Батч] Собрано: {len(raw)} тайтлов → обогащение AniList...")

        enriched = await enrich_with_anilist(raw)
        saved = upsert_anime(enriched)
        STATS["total_saved"] += len(saved)
        STATS["genres_done"] += 1

        elapsed = time.time() - t0
        print(
            f"[Батч] {name} готово: {len(saved)}/{len(raw)} новых/обновлённых "
            f"за {elapsed/60:.1f} мин"
        )
    except Exception as e:
        msg = f"{name}: {e}"
        STATS["errors"].append(msg)
        print(f"[Батч] ОШИБКА {msg}")


async def main() -> None:
    init_db()
    total_start = time.time()
    print("[J.A.R.V.I.S.] Ночной батч-парсинг запущен")
    print(f"Жанров в очереди: {len(GENRES)}  |  Годы: {YEAR_MIN}–{YEAR_MAX}")
    print("Обогащение: AniList (бесплатно, без лимитов)")

    for name, path in GENRES:
        await process_genre(name, path)
        # Пауза между жанрами чтобы не перегружать animevost.org
        await asyncio.sleep(5)

    elapsed = (time.time() - total_start) / 60
    print(f"\n{'='*60}")
    print(f"[J.A.R.V.I.S.] БАТЧ ЗАВЕРШЁН за {elapsed:.0f} мин")
    print(f"Жанров обработано : {STATS['genres_done']}/{len(GENRES)}")
    print(f"Тайтлов собрано   : {STATS['total_raw']}")
    print(f"Записей в БД      : {STATS['total_saved']}")
    if STATS["errors"]:
        print(f"Ошибки ({len(STATS['errors'])}):")
        for e in STATS["errors"]:
            print(f"  • {e}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
