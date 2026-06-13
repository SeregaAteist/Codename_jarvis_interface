"""Unit-тесты для LLMRouter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def test_router_singleton() -> None:
    from shared.llm import router as r

    r1 = r.get_router()
    r2 = r.get_router()
    assert r1 is r2


def test_resolve_known_role() -> None:
    from shared.llm.router import LLMRouter

    router = LLMRouter()
    provider, model = router.resolve("quick_analysis")
    assert provider == "gemini"
    assert model  # не пусто


def test_resolve_unknown_role_raises() -> None:
    from shared.llm.router import LLMRouter

    router = LLMRouter()
    with pytest.raises(ValueError, match="Неизвестная роль"):
        router.resolve("nonexistent_role_xyz")


@pytest.mark.asyncio
async def test_generate_calls_gemini() -> None:
    from shared.llm.router import LLMRouter

    router = LLMRouter()
    with patch("shared.llm.providers.gemini.generate", new_callable=AsyncMock), patch(
        "shared.errors.retry_with_backoff", new_callable=AsyncMock
    ) as mock_retry:
        mock_retry.return_value = "ответ gemini"
        result = await router.generate("quick_analysis", "тест")
    assert result == "ответ gemini"
    mock_retry.assert_called_once()


@pytest.mark.asyncio
async def test_module_level_generate_delegates_to_singleton() -> None:
    from shared.llm import router as r

    with patch.object(r.get_router(), "generate", new_callable=AsyncMock) as mock:
        mock.return_value = "результат"
        result = await r.generate("quick_analysis", "тест")
    assert result == "результат"
    mock.assert_called_once_with(
        "quick_analysis", "тест", on_progress=None, deadline_ts=None
    )


def test_gemini_pool_is_exported() -> None:
    from shared.llm.key_pool import SimplePool
    from shared.llm.router import gemini_pool

    assert isinstance(gemini_pool, SimplePool)
