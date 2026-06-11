"""Supervisor («Капитан») — Reasoning Core оркестрации задач.

Гибрид по риску (решение владельца):
  • read/notify (анализ, чтение, уведомления) → АВТО-раздача через registry.
  • RCE-уровень / изменение состояния (исполнение Claude Code, системные изменения,
    внешние отправки) → plan → approve (подтверждение владельца) — тот же паттерн,
    что уже работает в bot/task_handler. Незнакомая capability → безопасный дефолт APPROVE.

Регистрируется в core.registry как агент (name="captain"), слушает core.bus.
Подтверждение инжектируется коллбэком approve_callback(plan, task) -> awaitable[bool]
(бот подключит его к Telegram-кнопкам approve/cancel). Без коллбэка APPROVE-задачи
НЕ исполняются автоматически — возвращается статус pending_approval.
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Awaitable, Callable

import core.bus as bus
import core.registry as registry
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class Risk(str, Enum):
    AUTO = "auto"        # read/notify → авто
    APPROVE = "approve"  # RCE/изменение состояния → plan → approve


# Признаки capability по риску (подстрока в имени capability).
_READ_NOTIFY = ("analyze", "quick", "search", "fetch", "read", "notify",
                "weather", "rss", "recommend", "summar", "digest", "status")
_RCE = ("execute", "exec", "task", "shell", "deploy", "write", "delete",
        "system", "mac.control", "commit", "push", "send", "install")


def classify_risk(capability: str, payload: dict | None = None) -> Risk:
    cap = (capability or "").lower()
    if any(k in cap for k in _RCE):
        return Risk.APPROVE
    if any(k in cap for k in _READ_NOTIFY):
        return Risk.AUTO
    return Risk.APPROVE  # безопасный дефолт: незнакомое — через подтверждение


ApproveCb = Callable[[str, dict], Awaitable[bool]]


class Supervisor(BaseAgent):
    name = "captain"
    capabilities = ["orchestrate", "dispatch"]

    def __init__(self, approve_callback: ApproveCb | None = None) -> None:
        super().__init__()
        self._approve = approve_callback

    # BaseAgent-контракт (не основной путь; основной — dispatch_task)
    async def execute(self, task: str) -> str:
        return f"captain: задача принята — {task}"

    @staticmethod
    def _as_task(payload) -> str:
        return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

    async def _run(self, capability: str, payload) -> dict:
        await bus.emit("task.assigned", {"capability": capability})
        try:
            result = await registry.dispatch(capability, self._as_task(payload))
            await bus.emit("task.completed", {"capability": capability, "ok": True})
            return {"status": "done", "capability": capability, "result": result}
        except Exception as e:  # noqa: BLE001
            await bus.emit("task.failed", {"capability": capability, "error": str(e)})
            logger.error("[captain] '%s' упала: %s", capability, e)
            return {"status": "error", "capability": capability, "error": str(e)}

    async def _make_plan(self, capability: str, payload) -> str:
        return (f"📋 План (RCE-уровень, требуется подтверждение):\n"
                f"• capability: {capability}\n• данные: {self._as_task(payload)[:500]}")

    async def dispatch_task(self, capability: str, payload=None) -> dict:
        """Главный вход: классифицировать риск и раздать (авто) или провести через approve."""
        risk = classify_risk(capability, payload if isinstance(payload, dict) else None)
        await bus.emit("task.submitted", {"capability": capability, "risk": risk.value})

        if risk is Risk.AUTO:
            return await self._run(capability, payload)

        # APPROVE: plan → approve → execute
        plan = await self._make_plan(capability, payload)
        if self._approve is None:
            await bus.emit("task.pending_approval", {"capability": capability})
            return {"status": "pending_approval", "capability": capability, "plan": plan}
        approved = await self._approve(plan, {"capability": capability, "payload": payload})
        if not approved:
            await bus.emit("task.cancelled", {"capability": capability})
            return {"status": "cancelled", "capability": capability}
        return await self._run(capability, payload)

    def wire_bus(self) -> None:
        """Подписка на шину: событие 'task.request' → dispatch_task."""
        async def _on_request(data: dict) -> None:
            await self.dispatch_task(data.get("capability"), data.get("payload"))
        bus.on("task.request", _on_request)


# Единый экземпляр + регистрация в реестре и шине.
supervisor = Supervisor()


def register_supervisor(approve_callback: ApproveCb | None = None) -> Supervisor:
    """Зарегистрировать Капитана в registry + подписать на bus. approve_callback —
    подтверждение владельца (бот подключит к Telegram-кнопкам)."""
    if approve_callback is not None:
        supervisor._approve = approve_callback
    registry.register(supervisor)
    supervisor.wire_bus()
    logger.info("[captain] зарегистрирован, approve=%s", "on" if supervisor._approve else "off")
    return supervisor
