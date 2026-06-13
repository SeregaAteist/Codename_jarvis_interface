"""Pydantic модели для модуля Рафаил (материалы и обработанный контент)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ProcessedStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADED = "uploaded"


class Material(BaseModel):
    id: int
    title: str
    url: str
    domain: str
    track: str
    raw_content: str
    collected_at: datetime


class ProcessedSection(BaseModel):
    id: int
    material_id: int | None
    content_type: str
    track: str
    title: str
    content: str
    status: ProcessedStatus
    created_at: datetime
