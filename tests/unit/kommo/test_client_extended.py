"""Тесты расширенных методов KommoClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.kommo.client import KommoClient


@pytest.fixture
def client() -> KommoClient:
    return KommoClient(domain="test.kommo.com", token="test_token")


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json = lambda: payload
    resp.raise_for_status = lambda: None
    return resp


@pytest.mark.asyncio
async def test_get_leads_empty(client: KommoClient) -> None:
    payload = {"_embedded": {"leads": []}}
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response(payload)
        )
        leads = await client.get_leads()
    assert leads == []


@pytest.mark.asyncio
async def test_get_leads_with_status_filter(client: KommoClient) -> None:
    payload = {
        "_embedded": {
            "leads": [
                {
                    "id": 1,
                    "name": "Тест",
                    "status_id": 100,
                    "responsible_user_id": 5,
                    "pipeline_id": 10,
                }
            ]
        }
    }
    with patch("httpx.AsyncClient") as mock:
        get_mock = AsyncMock(return_value=_mock_response(payload))
        mock.return_value.__aenter__.return_value.get = get_mock
        leads = await client.get_leads(status_id=100)
    assert len(leads) == 1
    assert leads[0].id == 1
    call_params = get_mock.call_args.kwargs["params"]
    assert "filter[statuses][0][status_id]" in call_params


@pytest.mark.asyncio
async def test_get_users(client: KommoClient) -> None:
    payload = {"_embedded": {"users": [{"id": 1, "name": "Ольга"}]}}
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response(payload)
        )
        users = await client.get_users()
    assert len(users) == 1
    assert users[0]["name"] == "Ольга"


@pytest.mark.asyncio
async def test_get_pipelines(client: KommoClient) -> None:
    payload = {"_embedded": {"pipelines": [{"id": 1, "name": "Основная"}]}}
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response(payload)
        )
        pipelines = await client.get_pipelines()
    assert len(pipelines) == 1
    assert pipelines[0]["name"] == "Основная"


@pytest.mark.asyncio
async def test_search_leads_empty(client: KommoClient) -> None:
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response({"_embedded": {"leads": []}})
        )
        leads = await client.search_leads("тест")
    assert leads == []


@pytest.mark.asyncio
async def test_search_leads_found(client: KommoClient) -> None:
    payload = {
        "_embedded": {
            "leads": [
                {
                    "id": 42,
                    "name": "СЭС Одесса",
                    "status_id": 1,
                    "responsible_user_id": 2,
                    "pipeline_id": 3,
                }
            ]
        }
    }
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=_mock_response(payload)
        )
        leads = await client.search_leads("СЭС")
    assert len(leads) == 1
    assert leads[0].name == "СЭС Одесса"


@pytest.mark.asyncio
async def test_get_stale_leads(client: KommoClient) -> None:
    with patch("httpx.AsyncClient") as mock:
        get_mock = AsyncMock(return_value=_mock_response({"_embedded": {"leads": []}}))
        mock.return_value.__aenter__.return_value.get = get_mock
        leads = await client.get_stale_leads(days_inactive=14)
    assert leads == []
    call_params = get_mock.call_args.kwargs["params"]
    assert "filter[updated_at][to]" in call_params
