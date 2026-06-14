"""Типы событий и их схемы."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CallFinishedEvent:
    call_id: str
    phone: str
    duration: int
    disposition: str
    audio_url: str | None = None
    contact_id: int | None = None
    lead_id: int | None = None
    manager_sip: str | None = None
    ts: datetime = field(default_factory=datetime.now)


@dataclass
class CallAnalyzedEvent:
    call_id: str
    lead_id: int
    transcript: str
    summary: str
    agreements: list[str] = field(default_factory=list)
    ts: datetime = field(default_factory=datetime.now)


@dataclass
class LeadStaleEvent:
    lead_id: int
    lead_name: str
    responsible_user_id: int
    days_inactive: int
    ts: datetime = field(default_factory=datetime.now)
