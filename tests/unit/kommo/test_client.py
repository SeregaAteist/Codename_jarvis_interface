"""Тесты для KommoClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.kommo.client import KommoClient


@pytest.fixture
def client() -> KommoClient:
    return KommoClient(domain="test.kommo.com", token="test_token")


async def test_find_contact_by_phone_found(client: KommoClient) -> None:
    mock_response = {
        "_embedded": {
            "contacts": [
                {
                    "id": 123,
                    "name": "Тест",
                    "custom_fields_values": [{"values": [{"value": "+380939151888"}]}],
                }
            ]
        }
    }
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=MagicMock(
                json=lambda: mock_response, raise_for_status=lambda: None
            )
        )
        result = await client.find_contact_by_phone("+380939151888")
    assert result is not None
    assert result.id == 123
    assert result.name == "Тест"


async def test_find_contact_by_phone_not_found(client: KommoClient) -> None:
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=MagicMock(
                json=lambda: {"_embedded": {"contacts": []}},
                raise_for_status=lambda: None,
            )
        )
        result = await client.find_contact_by_phone("+380000000000")
    assert result is None


def test_get_lead_url(client: KommoClient) -> None:
    url = client.get_lead_url(12345)
    assert url == "https://test.kommo.com/leads/detail/12345"


async def test_add_note_calls_api(client: KommoClient) -> None:
    with patch("httpx.AsyncClient") as mock:
        post_mock = AsyncMock(return_value=MagicMock(raise_for_status=lambda: None))
        mock.return_value.__aenter__.return_value.post = post_mock
        await client.add_note(lead_id=999, text="тест")
    post_mock.assert_called_once()
    call_args = post_mock.call_args
    assert "/leads/999/notes" in call_args[0][0]
