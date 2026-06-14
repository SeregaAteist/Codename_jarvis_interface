"""Тесты для shared/models/jarvis.py."""

from __future__ import annotations

from datetime import datetime

from shared.models.jarvis import (
    AgentStatus,
    BriefingReport,
    CallSummary,
    ServiceStatus,
    SystemStatus,
)


def test_agent_status_values():
    assert AgentStatus.IDLE == "idle"
    assert AgentStatus.RUNNING == "running"
    assert AgentStatus.ERROR == "error"
    assert AgentStatus.STOPPED == "stopped"


def test_service_status_minimal():
    s = ServiceStatus(name="hud", pid=None, status=AgentStatus.STOPPED)
    assert s.name == "hud"
    assert s.pid is None
    assert s.exit_code == "0"
    assert s.uptime_seconds == 0


def test_service_status_full():
    s = ServiceStatus(
        name="api", pid=1234, status=AgentStatus.RUNNING, uptime_seconds=3600
    )
    assert s.pid == 1234
    assert s.status == AgentStatus.RUNNING
    assert s.uptime_seconds == 3600


def test_system_status():
    now = datetime.now()
    ss = SystemStatus(
        services=[
            ServiceStatus(name="api", pid=1, status=AgentStatus.RUNNING),
            ServiceStatus(name="mcp", pid=None, status=AgentStatus.STOPPED),
        ],
        total=2,
        running=1,
        stopped=1,
        timestamp=now,
    )
    assert ss.total == 2
    assert ss.running == 1
    assert len(ss.services) == 2


def test_briefing_report_defaults():
    now = datetime.now()
    r = BriefingReport(date=now)
    assert r.weather == ""
    assert r.news == []
    assert r.rafail_pending == 0
    assert r.calls_today == 0
    assert r.anime_catalog == 0


def test_briefing_report_full():
    now = datetime.now()
    r = BriefingReport(
        date=now,
        weather="Сонячно, +25°C",
        news=["новина 1", "новина 2"],
        rafail_pending=3,
        calls_today=15,
        anime_catalog=352,
    )
    assert r.weather == "Сонячно, +25°C"
    assert len(r.news) == 2
    assert r.anime_catalog == 352


def test_call_summary_defaults():
    s = CallSummary(
        call_id="c-001",
        phone="+380939151888",
        contact_name="Тест",
        lead_name="Угода тест",
        lead_url="https://example.com/leads/1",
        duration=120,
        summary="Обговорили СЕС 10кВт",
        next_step="Відправити КП",
    )
    assert s.effectiveness == "medium"
    assert s.objections == []
    assert s.agreements == []


def test_call_summary_full():
    s = CallSummary(
        call_id="c-002",
        phone="+380931234567",
        contact_name="Клієнт",
        lead_name="СЕС 15кВт",
        lead_url="https://example.com/leads/2",
        duration=300,
        summary="Зацікавлений, просить КП",
        next_step="Підготувати КП до п'ятниці",
        objections=["Дорого", "Довго"],
        agreements=["Зустріч у понеділок"],
        effectiveness="high",
    )
    assert len(s.objections) == 2
    assert s.effectiveness == "high"
    assert s.duration == 300
