"""Kitsu-агент: заглушка для проверки масштабируемости pipeline.

Включается через ENRICHERS_ENABLED=anilist,jikan,kitsu в .env —
без правок run_scan. Реальная интеграция kitsu.app — по необходимости.
"""
import logging

from agents.base_enricher import BaseEnricher

logger = logging.getLogger("kitsu")


class KitsuEnricher(BaseEnricher):
    name = "kitsu"
    priority = 2  # после AniList и Jikan

    async def enrich(self, items: list[dict]) -> list[dict]:
        logger.info("Заглушка: %d тайтлов пропущено без обогащения.", len(items))
        return items
