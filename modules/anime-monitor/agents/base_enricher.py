"""Базовый класс агентов обогащения метаданными.

Новый источник (Kitsu, Shikimori, ...) = один класс-наследник + одна строка
в реестре ENRICHERS (main.py). run_scan о конкретных агентах не знает.
Включение/отключение — через ENRICHERS_ENABLED в .env (без правок кода).
"""
from abc import ABC, abstractmethod


class BaseEnricher(ABC):
    name: str = "base"
    priority: int = 0  # меньше = выше приоритет (0 — основной, 1+ — fallback)

    @abstractmethod
    async def enrich(self, items: list[dict]) -> list[dict]:
        """Обогатить items метаданными. Уже заполненные поля не трогать."""

    def needs_enrichment(self, item: dict) -> bool:
        """True если item ещё нуждается в обогащении."""
        return not item.get("mal_score")
