import asyncio
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import cfg
from agents.db_agent import init_db, upsert_anime, log_episodes
from agents.scraper_agent import scrape_all_pages
from agents.jikan_agent import enrich_with_jikan
from agents.notify_agent import notify_new_episodes, notify_scan_complete, send_message
from bot.telegram_bot import build_app
from api.server import app as fastapi_app


async def run_scan() -> int:
    print("\n[J.A.R.V.I.S.] Запуск сканирования...")
    await send_message("🔍 Сканирование animevost.org запущено...")

    raw = await scrape_all_pages()
    if not raw:
        await send_message("⚠️ Парсер не вернул данных — сайт недоступен?")
        return 0

    enriched = await enrich_with_jikan(raw)
    new_items = upsert_anime(enriched)

    if new_items:
        log_episodes(new_items)
        await notify_new_episodes(new_items)

    await notify_scan_complete(len(enriched), len(new_items))
    print(f"[J.A.R.V.I.S.] Готово. Новинок: {len(new_items)}")
    return len(new_items)


async def main():
    init_db()
    print("[J.A.R.V.I.S.] Инициализация завершена.")
    hours_str = ", ".join(f"{h}:05" for h in cfg.SCAN_HOURS)
    print(f"[J.A.R.V.I.S.] Сканирование в {hours_str}")

    scheduler = AsyncIOScheduler()
    for hour in cfg.SCAN_HOURS:
        scheduler.add_job(
            run_scan,
            CronTrigger(hour=hour, minute=5),
            id=f"scan_{hour}",
            replace_existing=True,
        )
    scheduler.start()
    print(f"[Планировщик] Активен.")

    tg_app = build_app()
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)
    print("[Telegram] Бот запущен.")

    config = uvicorn.Config(
        fastapi_app,
        host=cfg.API_HOST,
        port=cfg.API_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    print(f"[API] FastAPI запущен на http://localhost:{cfg.API_PORT}")

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
