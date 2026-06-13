"""Pydantic модели для Kommo CRM."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KommoContact(BaseModel):
    id: int
    name: str
    phone: str = ""
    lead_ids: list[int] = []


class KommoLead(BaseModel):
    id: int
    name: str
    status_id: int
    responsible_user_id: int
    pipeline_id: int
    price: float = 0
    created_at: datetime | None = None


class KommoTask(BaseModel):
    id: int
    text: str
    lead_id: int
    responsible_user_id: int
    due_date: datetime | None = None
