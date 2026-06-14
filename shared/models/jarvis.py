"""Pydantic модели для системных сущностей JARVIS."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


class ServiceStatus(BaseModel):
    name: str
    pid: int | None
    status: AgentStatus
    exit_code: str = "0"
    uptime_seconds: int = 0


class SystemStatus(BaseModel):
    services: list[ServiceStatus]
    total: int
    running: int
    stopped: int
    timestamp: datetime


class BriefingReport(BaseModel):
    date: datetime
    weather: str = ""
    news: list[str] = []
    rafail_pending: int = 0
    calls_today: int = 0
    anime_catalog: int = 0


class CallSummary(BaseModel):
    call_id: str
    phone: str
    contact_name: str
    lead_name: str
    lead_url: str
    duration: int
    summary: str
    next_step: str
    objections: list[str] = []
    agreements: list[str] = []
    effectiveness: str = "medium"
