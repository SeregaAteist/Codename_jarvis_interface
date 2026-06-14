"""Unit-тесты для ScriptExtractor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.rafail.registry.script_registry import ScriptEntry, ScriptRegistry
from modules.rafail.researchers.script_extractor import ScriptExtractor


@pytest.fixture
def registry_dir(tmp_path: Path) -> Path:
    return tmp_path / "scripts"


@pytest.fixture
def extractor(registry_dir: Path) -> ScriptExtractor:
    with patch("modules.rafail.researchers.script_extractor.get_router") as mock_router:
        mock_router.return_value = MagicMock()
        ex = ScriptExtractor(registry_dir)
    return ex


@pytest.mark.asyncio
async def test_scan_empty_content_returns_empty(extractor: ScriptExtractor) -> None:
    result = await extractor.scan("")
    assert result == []


@pytest.mark.asyncio
async def test_scan_short_content_returns_empty(extractor: ScriptExtractor) -> None:
    result = await extractor.scan("короткий текст")
    assert result == []


@pytest.mark.asyncio
async def test_scan_creates_new_entry(registry_dir: Path) -> None:
    llm_response = """[
      {
        "key": "objection_expensive",
        "category": "objection",
        "title": "Заперечення: дорого",
        "variant_text": "Розумію вас, дозвольте пояснити цінність...",
        "source": "тест"
      }
    ]"""

    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=llm_response)

    with patch(
        "modules.rafail.researchers.script_extractor.get_router",
        return_value=mock_router,
    ):
        ex = ScriptExtractor(registry_dir)
        content = "Коли клієнт каже дорого, потрібно пояснити цінність продукту. " * 10
        keys = await ex.scan(content, source="test_material")

    assert "objection_expensive" in keys
    registry = ScriptRegistry(registry_dir)
    entry = registry.get("objection_expensive")
    assert entry is not None
    assert len(entry.variants) == 1


@pytest.mark.asyncio
async def test_scan_adds_variant_to_existing_entry(registry_dir: Path) -> None:
    registry = ScriptRegistry(registry_dir)
    existing = ScriptEntry(
        key="objection_expensive", category="objection", title="Дорого"
    )
    existing.add_variant("Старий варіант", "old_source")
    registry.save(existing)

    llm_response = """[
      {
        "key": "objection_expensive",
        "category": "objection",
        "title": "Заперечення: дорого",
        "variant_text": "Новий варіант відповіді...",
        "source": "new_material"
      }
    ]"""

    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=llm_response)

    with patch(
        "modules.rafail.researchers.script_extractor.get_router",
        return_value=mock_router,
    ):
        ex = ScriptExtractor(registry_dir)
        content = "Детальний матеріал про роботу з запереченням дорого. " * 10
        keys = await ex.scan(content, source="new_material")

    assert "objection_expensive" in keys
    loaded = registry.get("objection_expensive")
    assert len(loaded.variants) == 2


@pytest.mark.asyncio
async def test_scan_empty_llm_response(registry_dir: Path) -> None:
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value="[]")

    with patch(
        "modules.rafail.researchers.script_extractor.get_router",
        return_value=mock_router,
    ):
        ex = ScriptExtractor(registry_dir)
        content = "Довгий навчальний матеріал без скриптів продажів. " * 10
        keys = await ex.scan(content)

    assert keys == []


@pytest.mark.asyncio
async def test_scan_invalid_json_returns_empty(registry_dir: Path) -> None:
    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value="не JSON відповідь від LLM")

    with patch(
        "modules.rafail.researchers.script_extractor.get_router",
        return_value=mock_router,
    ):
        ex = ScriptExtractor(registry_dir)
        content = "Матеріал достатньої довжини для обробки. " * 10
        keys = await ex.scan(content)

    assert keys == []


@pytest.mark.asyncio
async def test_scan_skips_entry_without_key(registry_dir: Path) -> None:
    llm_response = """[{"category": "objection", "variant_text": "текст без ключа"}]"""

    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=llm_response)

    with patch(
        "modules.rafail.researchers.script_extractor.get_router",
        return_value=mock_router,
    ):
        ex = ScriptExtractor(registry_dir)
        content = "Навчальний матеріал достатньої довжини. " * 10
        keys = await ex.scan(content)

    assert keys == []
