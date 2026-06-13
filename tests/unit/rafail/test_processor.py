"""Тесты для RafailProcessor."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.models.rafail import Material


@pytest.fixture
def processor():  # type: ignore[no-untyped-def]
    with (
        patch("modules.rafail.processor.kb") as mock_kb,
        patch("modules.rafail.processor.get_settings") as mock_settings,
    ):
        mock_kb.get_setting.return_value = "trainee"
        mock_kb.get_prompt.return_value = "Check: {title}"
        mock_settings.return_value = MagicMock(
            rafail_model="gemini-2.5-flash",
            rafail_model_quality="gemini-2.5-flash",
        )
        from modules.rafail.processor import RafailProcessor

        p = RafailProcessor(level="trainee", dept="sales")
        p._model = "gemini-2.5-flash"
        p._model_quality = "gemini-2.5-flash"
        yield p


@pytest.fixture
def sample_material() -> Material:
    return Material(
        id=1,
        title="Solar panels guide",
        url="https://example.com",
        domain="example.com",
        track="sales",
        raw_content="Content about solar panels",
        collected_at=datetime(2026, 6, 1),
    )


async def test_is_relevant_yes(processor: object) -> None:
    from modules.rafail.processor import RafailProcessor

    p: RafailProcessor = processor  # type: ignore[assignment]
    p._generate = AsyncMock(return_value="YES, relevant")  # type: ignore[method-assign]
    assert await p.is_relevant("Solar panels guide") is True


async def test_is_relevant_no(processor: object) -> None:
    from modules.rafail.processor import RafailProcessor

    p: RafailProcessor = processor  # type: ignore[assignment]
    p._generate = AsyncMock(return_value="NO")  # type: ignore[method-assign]
    assert await p.is_relevant("Australian cricket news") is False


async def test_is_relevant_error_returns_true(processor: object) -> None:
    from modules.rafail.processor import RafailProcessor

    p: RafailProcessor = processor  # type: ignore[assignment]
    p._generate = AsyncMock(side_effect=Exception("API error"))  # type: ignore[method-assign]
    assert await p.is_relevant("anything") is True


async def test_make_section_delegates(
    processor: object, sample_material: Material
) -> None:
    from modules.rafail.processor import RafailProcessor

    p: RafailProcessor = processor  # type: ignore[assignment]
    with patch(
        "modules.rafail.processor.make_universal_section", new_callable=AsyncMock
    ) as mock_fn:
        mock_fn.return_value = 42
        result = await p.make_section(sample_material)
    assert result == 42
    mock_fn.assert_called_once_with(1, level="trainee", dept="sales")
