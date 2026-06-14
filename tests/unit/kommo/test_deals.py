"""Тесты для modules/kommo/deals.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import modules.kommo.deals as deals_mod


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
    client.patch = AsyncMock(return_value=resp)
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_get_lead():
    payload = {"id": 1, "name": "Угода тест", "price": 50000}
    with patch(
        "modules.kommo.deals.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await deals_mod.get_lead(1)
    assert result["id"] == 1
    assert result["price"] == 50000


@pytest.mark.asyncio
async def test_get_leads_returns_list():
    payload = {"_embedded": {"leads": [{"id": 10}, {"id": 11}]}}
    with patch(
        "modules.kommo.deals.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await deals_mod.get_leads(limit=10, page=1)
    assert len(result) == 2
    assert result[0]["id"] == 10


@pytest.mark.asyncio
async def test_get_leads_empty():
    payload = {"_embedded": {"leads": []}}
    with patch(
        "modules.kommo.deals.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await deals_mod.get_leads()
    assert result == []


@pytest.mark.asyncio
async def test_get_leads_missing_embedded():
    payload = {}
    with patch(
        "modules.kommo.deals.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await deals_mod.get_leads()
    assert result == []


@pytest.mark.asyncio
async def test_update_lead():
    payload = {"id": 5, "price": 99000}
    with patch(
        "modules.kommo.deals.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await deals_mod.update_lead(5, price=99000)
    assert result["price"] == 99000


@pytest.mark.asyncio
async def test_add_note():
    payload = {"_embedded": {"notes": [{"id": 77}]}}
    with patch(
        "modules.kommo.deals.httpx.AsyncClient", return_value=_make_client(payload)
    ):
        result = await deals_mod.add_note(5, "Клієнт передзвонить завтра")
    assert result == payload
