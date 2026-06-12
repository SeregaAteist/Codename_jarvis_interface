"""AnimeAgent (A-7): новые серии, рекомендации, Shikimori-синхронизация.

Отправка TG-уведомлений — через notify_func (инжектируется ботом):
    async notify_func(text: str, url: str | None) -> None
Без него check_new_episodes просто сохраняет серии и возвращает сводку.
"""
from __future__ import annotations

import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


def format_episode_notification(ep: dict) -> str:
    """Уведомление о новой серии (русский, по ТЗ)."""
    title_en = f" ({ep['title_en']})" if ep.get("title_en") else ""
    lines = [
        "🎬 Новая серия!",
        f"📺 {ep['title_ru']}{title_en}",
        f"📌 Сезон {ep.get('season', 1)}, серия {ep['episode_number']}: "
        f"{ep.get('episode_name', '')}",
    ]
    if ep.get("description"):
        lines.append(ep["description"][:300])
    if ep.get("score"):
        lines.append(f"⭐️ Ваша оценка: {ep['score']}/10")
    return "\n".join(lines)


class AnimeAgent(BaseAgent):
    name = "anime"
    icon = "🎌"
    capabilities = ["anime_check", "anime_recommend", "anime_sync"]

    def __init__(self, notify_func=None) -> None:
        super().__init__(timeout=120, retries=0)
        self.notify = notify_func

    async def execute(self, task: str) -> str:
        cmd = task.strip().split()[0].lower() if task.strip() else ""
        if cmd in ("check", "anime_check", "episodes"):
            return await self.check_new_episodes()
        if cmd in ("recommend", "anime_recommend"):
            return await self.get_recommendations()
        if cmd in ("sync", "shikimori", "anime_sync"):
            return await self.sync_shikimori()
        return f"Аниме: неизвестная команда '{cmd}'"

    async def check_new_episodes(self) -> str:
        """Dispatcher → matcher → уведомления в TG → mark_notified."""
        from core.parsers.dispatcher import ParserDispatcher
        from modules.anime import matcher

        parsed = await ParserDispatcher().run("animevost")
        if not parsed:
            return "⚠️ Animevost не ответил — проверка пропущена"

        new = matcher.find_new_episodes(parsed)
        if not new:
            return "✅ Новых серий нет"

        ids = matcher.save_episodes(new)
        notified = 0
        if self.notify is not None:
            for ep in new:
                try:
                    await self.notify(format_episode_notification(ep), ep.get("url") or None)
                    notified += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("[anime] уведомление: %s", e)
            matcher.mark_notified(ids)
        return f"🎬 Новых серий: {len(new)}, уведомлений отправлено: {notified}"

    async def get_recommendations(self) -> str:
        """Рекомендации по жанрам (нужно ≥5 тайтлов в watchlist)."""
        from modules.anime import watchlist as wl
        from modules.anime import recommender

        total = len(wl.get_all())
        if total < 5:
            return (f"🎯 Для рекомендаций нужно минимум 5 тайтлов в вотч-листе "
                    f"(сейчас {total}). Добавьте ещё {5 - total}.")
        recs = recommender.get_recommendations(limit=5)
        if not recs:
            return "🎯 Похожих тайтлов не нашлось — попробуйте после импорта каталога"
        lines = ["🎯 Рекомендации по вашим жанрам:"]
        for r in recs:
            rating = f" ★{r['rating_animevost']:.1f}" if r.get("rating_animevost") else ""
            lines.append(f"• {r['title_ru']}{rating}")
        return "\n".join(lines)

    async def sync_shikimori(self) -> str:
        from modules.anime import shikimori

        if not shikimori.is_available():
            return "🔄 Shikimori не подключён — добавьте SHIKIMORI_TOKEN в .env"
        result = await shikimori.sync_watchlist()
        return (f"🔄 Синхронизация Shikimori: добавлено {result.get('added', 0)}, "
                f"обновлено {result.get('updated', 0)}")
