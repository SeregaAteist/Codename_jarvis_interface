"""AgentRegistry — реестр всех агентов JARVIS."""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_registry: dict[str, type] = {}


def register(agent_class: type) -> type:
    """Декоратор для регистрации агента по его атрибуту name."""
    name = getattr(agent_class, "name", None)
    if not name or name == "base":
        return agent_class
    _registry[name] = agent_class
    logger.debug("[registry] зарегистрирован агент: %s", name)
    return agent_class


def get_agent(name: str) -> Any | None:
    """Получить экземпляр агента по имени."""
    cls = _registry.get(name)
    if not cls:
        logger.warning("[registry] агент не найден: %s", name)
        return None
    return cls()


def list_agents() -> list[str]:
    """Список всех зарегистрированных агентов."""
    return list(_registry.keys())


def load_all() -> None:
    """Импортировать все модули агентов, чтобы сработали @register декораторы."""
    agent_modules = [
        "agents.browser",
        "agents.briefing",
        "agents.anime",
        "agents.morning",
    ]
    for module in agent_modules:
        try:
            importlib.import_module(module)
        except ImportError as e:
            logger.warning("[registry] не удалось загрузить %s: %s", module, e)
