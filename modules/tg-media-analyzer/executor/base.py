"""Абстракция исполнителя задач Claude Code.

Драйверы: ssh (default, рабочий) и local (SQLite-очередь). Выбор — get_executor()
по CFG.EXECUTOR. Переключение на local — отдельным шагом после ручной проверки.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class TaskExecutor(ABC):
    @abstractmethod
    async def submit(self, task: dict) -> "int | str":
        """Поставить задачу в очередь, вернуть её id."""

    @abstractmethod
    async def status(self, task_id) -> str:
        """Статус задачи: pending | running | done | failed | unknown."""
