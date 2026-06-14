"""Smoke моста Капитан→TG: TelegramApprover (Future) + интеграция с Supervisor."""

import asyncio

from bot.supervisor_bridge import TelegramApprover

import core.bus as bus
import core.registry as registry
from agents.base import BaseAgent
from core.supervisor import Supervisor


class _Echo(BaseAgent):
    name = "echo"

    async def execute(self, task: str) -> str:
        return f"done:{task}"


async def _wait_key(sent: dict) -> str:
    for _ in range(100):
        if "key" in sent:
            return sent["key"]
        await asyncio.sleep(0.01)
    raise AssertionError("approve_callback не отправил план")


def test_approver_yes():
    async def run():
        sent = {}

        async def send(plan, key):
            sent["key"] = key

        ap = TelegramApprover(send)
        t = asyncio.ensure_future(ap("plan", {}))
        key = await _wait_key(sent)
        assert ap.resolve(key, True)
        assert await t is True

    asyncio.run(run())


def test_approver_no_and_stale():
    async def run():
        sent = {}

        async def send(plan, key):
            sent["key"] = key

        ap = TelegramApprover(send)
        t = asyncio.ensure_future(ap("plan", {}))
        key = await _wait_key(sent)
        assert ap.resolve(key, False)
        assert await t is False
        assert ap.resolve(key, True) is False  # повторный resolve → устарел

    asyncio.run(run())


def test_supervisor_approve_executes():
    async def run():
        registry.reset()
        bus.clear()
        registry.register(_Echo(), capabilities=["execute"])
        sent = {}

        async def send(plan, key):
            sent["key"] = key

        sup = Supervisor(approve_callback=TelegramApprover(send))
        ap = sup._approve
        done = []

        async def on_done(d):
            done.append(d.get("result"))

        bus.on("task.completed", on_done)
        task = asyncio.ensure_future(sup.dispatch_task("execute", "go"))
        key = await _wait_key(sent)
        ap.resolve(key, True)
        r = await task
        assert r["status"] == "done" and r["result"] == "done:go"
        assert done and "done:go" in done[0]

    asyncio.run(run())


def test_supervisor_cancel():
    async def run():
        registry.reset()
        bus.clear()
        registry.register(_Echo(), capabilities=["execute"])
        sent = {}

        async def send(plan, key):
            sent["key"] = key

        sup = Supervisor(approve_callback=TelegramApprover(send))
        task = asyncio.ensure_future(sup.dispatch_task("execute", "go"))
        key = await _wait_key(sent)
        sup._approve.resolve(key, False)
        r = await task
        assert r["status"] == "cancelled"

    asyncio.run(run())
