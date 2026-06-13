"""Тесты для CallAnalyzer и CallTranscriber."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.ringostat.analyzer import CallAnalyzer, CallTranscript


@pytest.fixture
def analyzer():
    with patch("modules.ringostat.analyzer.get_router"):
        a = CallAnalyzer()
        a._router = MagicMock()
        return a


@pytest.mark.asyncio
async def test_analyze_empty_transcript(analyzer):
    result = await analyzer.analyze(
        "", {"call_id": "test", "duration": 30, "caller_id": ""}
    )
    assert isinstance(result, CallTranscript)
    assert result.transcript == ""
    assert result.call_id == "test"


@pytest.mark.asyncio
async def test_analyze_returns_parsed_data(analyzer):
    analyzer._router.generate = AsyncMock(
        return_value=(
            '{"summary": "тест", "disposition": "successful", '
            '"objections": [], "agreements": ["зустріч"], '
            '"next_step": "відправити КП", "script_effectiveness": "high", '
            '"improvement_suggestions": []}'
        )
    )
    result = await analyzer.analyze(
        "МЕНЕДЖЕР: привіт\nКЛІЄНТ: привіт",
        {"call_id": "1", "duration": 60, "caller_id": "+380991234567"},
    )
    assert result.summary == "тест"
    assert result.disposition == "successful"
    assert result.next_step == "відправити КП"
    assert result.agreements == ["зустріч"]
    assert result.script_effectiveness == "high"


@pytest.mark.asyncio
async def test_analyze_invalid_json_falls_back(analyzer):
    analyzer._router.generate = AsyncMock(return_value="not json at all")
    result = await analyzer.analyze(
        "МЕНЕДЖЕР: текст",
        {"call_id": "2", "duration": 45, "caller_id": ""},
    )
    assert isinstance(result, CallTranscript)
    assert result.summary == "not json at all"[:200]


@pytest.mark.asyncio
async def test_analyze_history_empty(analyzer):
    result = await analyzer.analyze_history(42, [])
    assert result == ""


@pytest.mark.asyncio
async def test_analyze_history_calls_router(analyzer):
    analyzer._router.generate = AsyncMock(return_value="досьє клієнта")
    result = await analyzer.analyze_history(10, ["транскрипт 1", "транскрипт 2"])
    assert result == "досьє клієнта"
    analyzer._router.generate.assert_called_once()
    call_args = analyzer._router.generate.call_args
    assert call_args[0][0] == "quick_analysis"
    assert "угоді #10" in call_args[0][1]
