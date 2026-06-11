"""Smoke Капитана: классификация риска + гибрид авто / plan→approve."""
import asyncio

import core.bus as bus
import core.registry as registry
from agents.base import BaseAgent
from core.supervisor import Risk, Supervisor, classify_risk, register_supervisor


class _Echo(BaseAgent):
    name = "echo"

    async def execute(self, task: str) -> str:
        return f"done:{task}"


def test_classify_risk():
    assert classify_risk("quick_analysis") is Risk.AUTO
    assert classify_risk("notify_user") is Risk.AUTO
    assert classify_risk("execute_task") is Risk.APPROVE
    assert classify_risk("mac.control") is Risk.APPROVE
    assert classify_risk("frobnicate") is Risk.APPROVE  # незнакомое → безопасный дефолт


def test_auto_dispatch():
    async def run():
        registry.reset(); bus.clear()
        registry.register(_Echo(), capabilities=["analyze"])
        sup = Supervisor()
        events = []
        async def on_done(d): events.append("completed")
        bus.on("task.completed", on_done)
        r = await sup.dispatch_task("analyze", "payload")
        assert r["status"] == "done" and r["result"] == "done:payload"
        assert "completed" in events
    asyncio.run(run())


def test_approve_required_no_callback():
    async def run():
        registry.reset(); bus.clear()
        registry.register(_Echo(), capabilities=["execute"])
        sup = Supervisor()  # без approve-коллбэка
        r = await sup.dispatch_task("execute", {"cmd": "rm"})
        assert r["status"] == "pending_approval"  # RCE без подтверждения НЕ исполняется
        assert "plan" in r
    asyncio.run(run())


def test_approve_callback_yes_no():
    async def run():
        registry.reset(); bus.clear()
        registry.register(_Echo(), capabilities=["execute"])

        async def approve_yes(plan, task): return True
        async def approve_no(plan, task): return False

        sup_yes = Supervisor(approve_callback=approve_yes)
        r1 = await sup_yes.dispatch_task("execute", "go")
        assert r1["status"] == "done"

        sup_no = Supervisor(approve_callback=approve_no)
        r2 = await sup_no.dispatch_task("execute", "go")
        assert r2["status"] == "cancelled"
    asyncio.run(run())


def test_register_and_bus():
    async def run():
        registry.reset(); bus.clear()
        registry.register(_Echo(), capabilities=["analyze"])
        sup = register_supervisor()
        assert "captain" in [s["name"] for s in registry.all_statuses()]
        # через шину: task.request → dispatch
        await bus.emit("task.request", {"capability": "analyze", "payload": "via-bus"})
    asyncio.run(run())
