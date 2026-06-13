"""Тесты для RingostatWebhookHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.ringostat.webhook import RingostatWebhookHandler


@pytest.fixture
def handler() -> RingostatWebhookHandler:
    kommo = MagicMock()
    notifier = MagicMock()
    h = RingostatWebhookHandler(kommo=kommo, notifier=notifier)
    h._secret = "test-secret"
    return h


def test_verify_token_valid(handler: RingostatWebhookHandler) -> None:
    assert handler.verify_token("test-secret") is True


def test_verify_token_invalid(handler: RingostatWebhookHandler) -> None:
    assert handler.verify_token("wrong") is False


def test_verify_token_none(handler: RingostatWebhookHandler) -> None:
    assert handler.verify_token(None) is False


async def test_handle_no_phone(handler: RingostatWebhookHandler) -> None:
    result = await handler.handle({})
    assert result["status"] == "skip"


async def test_handle_unknown_contact(handler: RingostatWebhookHandler) -> None:
    handler._kommo.find_contact_by_phone = AsyncMock(return_value=None)
    handler._notifier.notify_unknown = AsyncMock()
    result = await handler.handle(
        {"caller_id": "+380000000000", "disposition": "MISSED"}
    )
    assert result["status"] == "unknown_contact"
    handler._notifier.notify_unknown.assert_called_once_with("+380000000000")


async def test_handle_answered_goes_to_topic(handler: RingostatWebhookHandler) -> None:
    contact = MagicMock(id=1, name="Тест")
    lead = MagicMock(id=100, name="Сделка")
    handler._kommo.find_contact_by_phone = AsyncMock(return_value=contact)
    handler._kommo.get_contact_leads = AsyncMock(return_value=[lead])
    handler._kommo.get_lead_url = MagicMock(
        return_value="https://example.com/leads/100"
    )
    handler._notifier.notify_call = AsyncMock()

    await handler.handle({"caller_id": "+380939151888", "disposition": "ANSWERED"})

    call_kwargs = handler._notifier.notify_call.call_args.kwargs
    assert call_kwargs["is_urgent"] is False


async def test_handle_missed_goes_to_personal(handler: RingostatWebhookHandler) -> None:
    contact = MagicMock(id=1, name="Тест")
    handler._kommo.find_contact_by_phone = AsyncMock(return_value=contact)
    handler._kommo.get_contact_leads = AsyncMock(return_value=[])
    handler._kommo.get_lead_url = MagicMock(return_value="")
    handler._notifier.notify_call = AsyncMock()

    await handler.handle({"caller_id": "+380939151888", "disposition": "NO ANSWER"})

    call_kwargs = handler._notifier.notify_call.call_args.kwargs
    assert call_kwargs["is_urgent"] is True
