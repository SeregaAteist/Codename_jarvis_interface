import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn
from agents.anilist_agent import AniListEnricher
from agents.base_enricher import BaseEnricher
from agents.db_agent import init_db, log_episodes, upsert_anime
from agents.jikan_agent import JikanEnricher
from agents.kitsu_agent import KitsuEnricher
from agents.notify_agent import notify_new_episodes, notify_scan_complete, send_message
from agents.scraper_agent import scrape_all_pages
from api.server import app as fastapi_app
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot.telegram_bot import build_app
from config import cfg


def _setup_logging() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "anime-monitor.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])


_setup_logging()
logger = logging.getLogger("main")

# Реестр агентов обогащения. Новый источник = класс + строка здесь.
# Фактический состав управляется ENRICHERS_ENABLED в .env (по name).
ENRICHERS: list[BaseEnricher] = [
    AniListEnricher(),
    JikanEnricher(),  # fallback автоматически (priority=1)
    KitsuEnricher(),  # заглушка (выключена, пока нет в ENRICHERS_ENABLED)
]


def active_enrichers() -> list[BaseEnricher]:
    enabled = set(cfg.ENRICHERS_ENABLED)
    return sorted(
        (e for e in ENRICHERS if e.name in enabled),
        key=lambda e: e.priority,
    )


async def enrich_all(items: list[dict]) -> list[dict]:
    """Прогнать items через цепочку enrichers по приоритету.

    Каждому агенту отдаются только тайтлы, ещё нуждающиеся в обогащении
    (dict мутируется на месте — fallback-агент дозаполняет пропуски).
    """
    for enricher in active_enrichers():
        missing = [i for i in items if enricher.needs_enrichment(i)]
        if not missing:
            break
        logger.info("[%s] обогащение: %d тайтлов", enricher.name, len(missing))
        try:
            await asyncio.wait_for(enricher.enrich(missing), timeout=30)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("[%s] пропущен: %s", enricher.name, e)
    return items


async def run_scan() -> int:
    logger.info("Запуск сканирования...")
    await send_message("🔍 Сканирование animevost.org запущено...")

    raw = await scrape_all_pages()
    if not raw:
        await send_message("⚠️ Парсер не вернул данных — сайт недоступен?")
        return 0

    enriched = await enrich_all(raw)
    new_items = upsert_anime(enriched)

    if new_items:
        log_episodes(new_items)
        await notify_new_episodes(new_items)

    await notify_scan_complete(len(enriched), len(new_items))
    logger.info("Готово. Новинок: %d", len(new_items))
    return len(new_items)


async def main():
    init_db()
    logger.info("Инициализация завершена.")
    hours_str = ", ".join(f"{h}:05" for h in cfg.SCAN_HOURS)
    logger.info("Сканирование в %s", hours_str)

    scheduler = AsyncIOScheduler()
    for hour in cfg.SCAN_HOURS:
        scheduler.add_job(
            run_scan,
            CronTrigger(hour=hour, minute=5),
            id=f"scan_{hour}",
            replace_existing=True,
        )
    scheduler.start()
    logger.info("[Планировщик] Активен.")

    tg_app = build_app()
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)
    logger.info("[Telegram] Бот запущен.")

    config = uvicorn.Config(
        fastapi_app,
        host=cfg.API_HOST,
        port=cfg.API_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    logger.info("[API] FastAPI запущен на http://localhost:%d", cfg.API_PORT)

    await send_message(
        "⚡ <b>J.A.R.V.I.S. Anime Monitor запущен</b>\n"
        f"Сканирование: {', '.join(f'{h}:05' for h in cfg.SCAN_HOURS)}\n"
        "Нажмите /start для управления."
    )

    await server.serve()

    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
