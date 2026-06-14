"""Маппинг SIP/телефон → Kommo user → TG id (shared/config/modules/ringostat.yaml)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_PATH = (
    Path(os.getenv("JARVIS_ROOT", "~/Projects/jarvis")).expanduser()
    / "shared/config/modules/ringostat.yaml"
)


def load_employees() -> list[dict]:
    if not CONFIG_PATH.exists():
        return []
    return yaml.safe_load(CONFIG_PATH.read_text()).get("employees", [])


def find_by_sip(sip: str) -> dict | None:
    for emp in load_employees():
        if str(emp.get("sip", "")) == str(sip):
            return emp
    return None


def find_by_phone(phone: str) -> dict | None:
    clean = "".join(filter(str.isdigit, str(phone)))[-10:]
    if not clean:
        return None
    for emp in load_employees():
        if clean in "".join(filter(str.isdigit, str(emp.get("phone", "")))):
            return emp
    return None


def find_by_kommo_id(kommo_user_id: int) -> dict | None:
    for emp in load_employees():
        if emp.get("kommo_user_id") == kommo_user_id:
            return emp
    return None


def find_by_telegram_id(telegram_id: int) -> dict | None:
    for emp in load_employees():
        if emp.get("telegram_id") == telegram_id:
            return emp
    return None


def get_owner() -> dict | None:
    for emp in load_employees():
        if emp.get("is_owner"):
            return emp
    return None
