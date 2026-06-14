"""Реестр агентов: регистрация, диспетчеризация по capability, телеметрия для HUD.

Работает поверх СУЩЕСТВУЮЩЕГО production-ready agents.base.BaseAgent
(execute/run со встроенными timeout + retry + exponential backoff).
BaseAgent НЕ изменяется:
- capabilities задаются при регистрации (или читаются из атрибута агента, если есть);
- статус (idle/busy/error) трекается здесь, в реестре, а не в самом агенте.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base import BaseAgent

logger = logging.getLogger(__name__)

_agents: dict[str, BaseAgent] = {}
_caps: dict[str, BaseAgent] = {}
_agent_caps: dict[str, list[str]] = {}
_status: dict[str, str] = {}  # name -> idle | busy | error


def register(agent: BaseAgent, capabilities: list[str] | None = None) -> BaseAgent:
    """Зарегистрировать агента. capabilities — явно или из atтрибута agent.capabilities."""
    caps = (
        capabilities
        if capabilities is not None
        else list(getattr(agent, "capabilities", []))
    )
    _agents[agent.name] = agent
    _agent_caps[agent.name] = caps
    _status.setdefault(agent.name, "idle")
    for cap in caps:
        _caps[cap] = agent
    logger.info("[registry] зарегистрирован '%s' caps=%s", agent.name, caps)
    return agent


def get_by_capability(cap: str) -> BaseAgent:
    if cap not in _caps:
        raise KeyError(f"Нет агента с capability '{cap}'. Доступны: {sorted(_caps)}")
    return _caps[cap]


async def dispatch(cap: str, task: str) -> str:
    """Найти агента по capability и выполнить задачу через его run() (timeout+retry внутри)."""
    agent = get_by_capability(cap)
    _status[agent.name] = "busy"
    try:
        result = await agent.run(task)
        _status[agent.name] = "idle"
        return result
    except Exception:
        _status[agent.name] = "error"
        raise


def all_statuses() -> list[dict]:
    """Телеметрия для HUD: имя, статус, capabilities, доступность."""
    return [
        {
            "name": name,
            "status": _status.get(name, "idle"),
            "capabilities": _agent_caps.get(name, []),
            "available": agent.is_available(),
        }
        for name, agent in _agents.items()
    ]


def reset() -> None:
    """Очистить реестр (для тестов)."""
    _agents.clear()
    _caps.clear()
    _agent_caps.clear()
    _status.clear()
