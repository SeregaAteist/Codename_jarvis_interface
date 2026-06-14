"""Планировщик задач с драйверной моделью.

Сейчас один драйвер — APSchedulerDriver. Интерфейс SchedulerDriver заложен под
будущие драйверы (n8n/cron) без переписывания вызывающего кода.

API: schedule(job_id, cron_expr, callback), list_jobs(), remove(job_id), start().
Первая задача — заглушка morning_briefing (лог в 08:00), наполнится в Фазе 11.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class SchedulerDriver(ABC):
    @abstractmethod
    def schedule(self, job_id: str, cron_expr: str, callback: Callable) -> None:
        """Поставить задачу по cron-выражению (5 полей)."""

    @abstractmethod
    def remove(self, job_id: str) -> None: ...

    @abstractmethod
    def list_jobs(self) -> list[str]: ...

    @abstractmethod
    def start(self) -> None: ...


class APSchedulerDriver(SchedulerDriver):
    def __init__(self) -> None:
        self._sched = AsyncIOScheduler()

    def schedule(self, job_id: str, cron_expr: str, callback: Callable) -> None:
        self._sched.add_job(
            callback,
            CronTrigger.from_crontab(cron_expr),
            id=job_id,
            replace_existing=True,
        )
        logger.info("[scheduler] job '%s' @ cron '%s'", job_id, cron_expr)

    def remove(self, job_id: str) -> None:
        self._sched.remove_job(job_id)
        logger.info("[scheduler] job '%s' удалён", job_id)

    def list_jobs(self) -> list[str]:
        return [j.id for j in self._sched.get_jobs()]

    def start(self) -> None:
        self._sched.start()
        logger.info("[scheduler] запущен, jobs=%s", self.list_jobs())


# Единый экземпляр планировщика (драйвер можно заменить позже).
scheduler: SchedulerDriver = APSchedulerDriver()


async def morning_briefing() -> None:
    """Утренний брифинг (Фаза 11): Reddit RSS → Gemini-резюме → Telegram владельцу."""
    from agents.briefing import BriefingAgent

    await BriefingAgent().run_briefing()


async def anime_check() -> None:
    """Проверка новых серий (A-11): dispatcher → matcher → уведомление владельцу."""
    from telegram import Bot

    from agents.anime import AnimeAgent
    from shared.config import CFG

    async def notify(text: str, url: str | None) -> None:
        bot = Bot(CFG.TELEGRAM_TOKEN)
        async with bot:
            await bot.send_message(chat_id=CFG.OWNER_USER_ID, text=text)

    result = await AnimeAgent(notify_func=notify).check_new_episodes()
    logger.info("[scheduler] anime_check: %s", result)


async def rafail_collect() -> None:
    """Ежедневный сбор материалов Рафаила (RF-13)."""
    from agents.rafail import RafailAgent

    result = await RafailAgent().daily_collect()
    logger.info("[scheduler] rafail_collect: %s", result)


async def rafail_weekly_report() -> None:
    """Еженедельный отчёт по обучению — владельцу в TG (RF-13)."""
    from telegram import Bot

    from agents.rafail import RafailAgent
    from shared.config import CFG

    try:
        report = await RafailAgent().generate_progress_report()
    except Exception as e:  # noqa: BLE001
        report = f"⚠️ Отчёт по обучению не собран: {e}"
    bot = Bot(CFG.TELEGRAM_TOKEN)
    async with bot:
        await bot.send_message(chat_id=CFG.OWNER_USER_ID, text=report[:4000])


def register_default_jobs() -> None:
    """Стартовые задачи. Вызвать перед scheduler.start()."""
    scheduler.schedule(
        "morning_briefing", "0 8 * * *", morning_briefing
    )  # 08:00 ежедневно
    scheduler.schedule("anime_check", "0 */3 * * *", anime_check)  # каждые 3 часа
    scheduler.schedule("rafail_collect", "0 8 * * *", rafail_collect)  # 08:00 ежедневно
    scheduler.schedule("rafail_report", "0 9 * * 1", rafail_weekly_report)  # пн 09:00


def main() -> None:
    import asyncio

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    register_default_jobs()
    scheduler.start()
    logger.info("scheduler демо запущен. Jobs: %s", scheduler.list_jobs())
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
