"""Unit-тесты для modules/kommo/tasks.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def stale_leads() -> list[dict]:
    return [
        {"id": 101, "name": "ТОВ Сонце", "responsible_user_id": 5},
        {"id": 102, "name": "Іваненко Петро", "responsible_user_id": 7},
        {"id": 103, "name": "", "responsible_user_id": 0},
    ]


@pytest.mark.asyncio
async def test_analyze_stale_leads_creates_tasks(stale_leads: list[dict]) -> None:
    from modules.kommo.tasks import analyze_stale_leads

    mock_client = MagicMock()
    mock_client.create_task = AsyncMock(return_value=None)

    with (
        patch(
            "modules.kommo.tasks.get_stale_leads",
            new=AsyncMock(return_value=stale_leads),
        ),
        patch("modules.kommo.client.KommoClient", return_value=mock_client),
    ):
        results = await analyze_stale_leads(days_inactive=7)

    assert len(results) == 3
    assert mock_client.create_task.call_count == 3


@pytest.mark.asyncio
async def test_analyze_stale_leads_returns_correct_structure(
    stale_leads: list[dict],
) -> None:
    from modules.kommo.tasks import analyze_stale_leads

    mock_client = MagicMock()
    mock_client.create_task = AsyncMock(return_value=None)

    with (
        patch(
            "modules.kommo.tasks.get_stale_leads",
            new=AsyncMock(return_value=stale_leads),
        ),
        patch("modules.kommo.client.KommoClient", return_value=mock_client),
    ):
        results = await analyze_stale_leads(days_inactive=7)

    first = results[0]
    assert first["lead_id"] == 101
    assert first["lead_name"] == "ТОВ Сонце"
    assert first["days_inactive"] == 7


@pytest.mark.asyncio
async def test_analyze_stale_leads_empty_returns_empty() -> None:
    from modules.kommo.tasks import analyze_stale_leads

    mock_client = MagicMock()
    mock_client.create_task = AsyncMock(return_value=None)

    with (
        patch("modules.kommo.tasks.get_stale_leads", new=AsyncMock(return_value=[])),
        patch("modules.kommo.client.KommoClient", return_value=mock_client),
    ):
        results = await analyze_stale_leads(days_inactive=7)

    assert results == []
    mock_client.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_stale_leads_skips_failed_task(stale_leads: list[dict]) -> None:
    from modules.kommo.tasks import analyze_stale_leads

    mock_client = MagicMock()
    mock_client.create_task = AsyncMock(
        side_effect=[Exception("Kommo 500"), None, None]
    )

    with (
        patch(
            "modules.kommo.tasks.get_stale_leads",
            new=AsyncMock(return_value=stale_leads),
        ),
        patch("modules.kommo.client.KommoClient", return_value=mock_client),
    ):
        results = await analyze_stale_leads(days_inactive=7)

    # Первый лид упал — пропускаем, остальные добавлены
    assert len(results) == 2
    assert results[0]["lead_id"] == 102


@pytest.mark.asyncio
async def test_analyze_stale_leads_task_text_mentions_days(
    stale_leads: list[dict],
) -> None:
    from modules.kommo.tasks import analyze_stale_leads

    mock_client = MagicMock()
    mock_client.create_task = AsyncMock(return_value=None)

    with (
        patch(
            "modules.kommo.tasks.get_stale_leads",
            new=AsyncMock(return_value=stale_leads[:1]),
        ),
        patch("modules.kommo.client.KommoClient", return_value=mock_client),
    ):
        await analyze_stale_leads(days_inactive=14)

    call_kwargs = mock_client.create_task.call_args
    text_arg = call_kwargs.kwargs.get("text") or call_kwargs.args[1]
    assert "14" in text_arg


@pytest.mark.asyncio
async def test_create_task_calls_api(monkeypatch) -> None:
    """create_task() формирует корректный payload для Kommo API."""
    from modules.kommo.tasks import create_task

    monkeypatch.setenv("KOMMO_DOMAIN", "test.kommo.com")
    monkeypatch.setenv("KOMMO_TOKEN", "test_token")

    captured: dict = {}

    mock_response = MagicMock()
    mock_response.json.return_value = {}

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    async def fake_post(url, headers, json):
        captured["url"] = url
        captured["json"] = json
        return mock_response

    mock_http.post = fake_post

    with patch("modules.kommo.tasks.httpx.AsyncClient", return_value=mock_http):
        await create_task(
            lead_id=99,
            text="Реанімація",
            responsible_user_id=5,
            days_until_due=1,
        )

    assert "tasks" in captured["url"]
    payload = captured["json"]
    assert isinstance(payload, list)
    assert payload[0]["entity_id"] == 99
    assert payload[0]["text"] == "Реанімація"
