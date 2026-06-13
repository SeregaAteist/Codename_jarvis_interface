"""Pydantic модели для Ringostat webhook событий."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CallDisposition(str, Enum):
    ANSWERED = "ANSWERED"
    NO_ANSWER = "NO ANSWER"
    BUSY = "BUSY"
    FAILED = "FAILED"


class CallEvent(BaseModel):
    call_id: str = ""
    caller_id: str
    called_id: str = ""
    duration: int = 0
    disposition: CallDisposition
    audio_url: str | None = None
    manager_sip: str | None = None
