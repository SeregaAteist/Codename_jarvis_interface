"""Тесты для modules/kommo/contacts.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import modules.kommo.contacts as contacts_mod


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("KOMMO_TOKEN", "test_token")
    monkeypatch.setenv("KOMMO_DOMAIN", "test.kommo.com")


def _make_client(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_find_by_phone_found():
    payload = {
        "_embedded": {
            "contacts": [
                {
                    "id": 1,
                    "name": "Тест",
                    "custom_fields_values": [{"values": [{"value": "+380939151888"}]}],
                }
            ]
        }
    }
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.find_by_phone("+380939151888")
    assert result is not None
    assert result["id"] == 1


@pytest.mark.asyncio
async def test_find_by_phone_no_match():
    payload = {
        "_embedded": {
            "contacts": [
                {
                    "id": 2,
                    "name": "Інший",
                    "custom_fields_values": [{"values": [{"value": "+380000000000"}]}],
                }
            ]
        }
    }
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.find_by_phone("+380939151888")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_phone_empty_contacts():
    payload = {"_embedded": {"contacts": []}}
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.find_by_phone("+380939151888")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_phone_no_custom_fields():
    payload = {
        "_embedded": {
            "contacts": [{"id": 3, "name": "Без полів", "custom_fields_values": None}]
        }
    }
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.find_by_phone("+380939151888")
    assert result is None


@pytest.mark.asyncio
async def test_get_contact_leads():
    payload = {"_embedded": {"leads": [{"id": 101}, {"id": 102}]}}
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.get_contact_leads(42)
    assert len(result) == 2
    assert result[0]["id"] == 101


@pytest.mark.asyncio
async def test_get_contact_leads_empty():
    payload = {"_embedded": {"leads": []}}
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.get_contact_leads(99)
    assert result == []


@pytest.mark.asyncio
async def test_create_contact():
    payload = {"_embedded": {"contacts": [{"id": 200, "name": "Новий"}]}}
    with patch(
        "modules.kommo.contacts.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await contacts_mod.create_contact("Новий", "+380939999999")
    assert result == payload
