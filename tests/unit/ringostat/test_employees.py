"""Тесты для modules/ringostat/employees.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.ringostat.employees import (
    find_by_kommo_id,
    find_by_phone,
    find_by_sip,
    find_by_telegram_id,
    get_owner,
    load_employees,
)

SAMPLE_EMPLOYEES = [
    {
        "name": "Sergey",
        "sip": "sergey",
        "phone": "+380939151888",
        "kommo_user_id": 15032975,
        "telegram_id": 374728252,
        "is_owner": True,
        "is_active": True,
    },
    {
        "name": "Ольга",
        "sip": "olga",
        "phone": "+380684883943",
        "kommo_user_id": 6006577,
        "telegram_id": 0,
        "is_owner": False,
        "is_active": True,
    },
    {
        "name": "Стажер",
        "sip": "",
        "phone": "",
        "kommo_user_id": 10603371,
        "telegram_id": 0,
        "is_owner": False,
        "is_active": False,
    },
]


@pytest.fixture
def mock_employees():
    with patch(
        "modules.ringostat.employees.load_employees", return_value=SAMPLE_EMPLOYEES
    ):
        yield


def test_load_employees_missing_file(tmp_path):
    with patch("modules.ringostat.employees.CONFIG_PATH", tmp_path / "missing.yaml"):
        result = load_employees()
    assert result == []


def test_load_employees_returns_list(tmp_path):
    import yaml

    cfg = tmp_path / "ringostat.yaml"
    cfg.write_text(yaml.dump({"employees": SAMPLE_EMPLOYEES}))
    with patch("modules.ringostat.employees.CONFIG_PATH", cfg):
        result = load_employees()
    assert len(result) == 3
    assert result[0]["name"] == "Sergey"


# ── find_by_sip ──────────────────────────────────────────────────────────────


def test_find_by_sip_found(mock_employees):
    result = find_by_sip("sergey")
    assert result is not None
    assert result["name"] == "Sergey"


def test_find_by_sip_not_found(mock_employees):
    result = find_by_sip("nonexistent")
    assert result is None


def test_find_by_sip_empty_matches_empty_sip(mock_employees):
    # Стажер має порожній sip — пошук "" знайде його
    result = find_by_sip("")
    assert result is not None
    assert result["name"] == "Стажер"


# ── find_by_phone ─────────────────────────────────────────────────────────────


def test_find_by_phone_found(mock_employees):
    result = find_by_phone("+380939151888")
    assert result is not None
    assert result["name"] == "Sergey"


def test_find_by_phone_partial(mock_employees):
    result = find_by_phone("0939151888")
    assert result is not None
    assert result["name"] == "Sergey"


def test_find_by_phone_not_found(mock_employees):
    result = find_by_phone("+380000000000")
    assert result is None


def test_find_by_phone_empty(mock_employees):
    result = find_by_phone("")
    assert result is None


def test_find_by_phone_no_digits(mock_employees):
    result = find_by_phone("abc")
    assert result is None


# ── find_by_kommo_id ──────────────────────────────────────────────────────────


def test_find_by_kommo_id_found(mock_employees):
    result = find_by_kommo_id(15032975)
    assert result is not None
    assert result["name"] == "Sergey"


def test_find_by_kommo_id_other_user(mock_employees):
    result = find_by_kommo_id(6006577)
    assert result is not None
    assert result["name"] == "Ольга"


def test_find_by_kommo_id_not_found(mock_employees):
    result = find_by_kommo_id(99999999)
    assert result is None


# ── find_by_telegram_id ───────────────────────────────────────────────────────


def test_find_by_telegram_id_found(mock_employees):
    result = find_by_telegram_id(374728252)
    assert result is not None
    assert result["name"] == "Sergey"


def test_find_by_telegram_id_zero_not_found(mock_employees):
    result = find_by_telegram_id(0)
    # 0 matches Ольга and Стажер — returns first match
    assert result is not None
    assert result["telegram_id"] == 0


def test_find_by_telegram_id_not_found(mock_employees):
    result = find_by_telegram_id(999999)
    assert result is None


# ── get_owner ─────────────────────────────────────────────────────────────────


def test_get_owner_found(mock_employees):
    result = get_owner()
    assert result is not None
    assert result["is_owner"] is True
    assert result["name"] == "Sergey"


def test_get_owner_none_when_no_owner():
    employees_no_owner = [
        {"name": "Ольга", "kommo_user_id": 1, "is_owner": False, "telegram_id": 0},
    ]
    with patch(
        "modules.ringostat.employees.load_employees", return_value=employees_no_owner
    ):
        result = get_owner()
    assert result is None
