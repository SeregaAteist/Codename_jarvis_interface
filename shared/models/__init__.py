"""Pydantic модели данных JARVIS."""

from shared.models.kommo import KommoContact, KommoLead, KommoTask
from shared.models.rafail import Material, ProcessedSection, ProcessedStatus
from shared.models.ringostat import CallDisposition, CallEvent

__all__ = [
    "KommoContact",
    "KommoLead",
    "KommoTask",
    "CallEvent",
    "CallDisposition",
    "Material",
    "ProcessedSection",
    "ProcessedStatus",
]
