"""Unit-тесты для ScriptAnalyzer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from modules.rafail.registry.script_registry import ScriptEntry, ScriptRegistry
from modules.rafail.researchers.script_analyzer import ScriptAnalyzer


@pytest.fixture
def registry_dir(tmp_path: Path) -> Path:
    d = tmp_path / "scripts"
    d.mkdir()
    return d


@pytest.fixture
def populated_registry(registry_dir: Path) -> ScriptRegistry:
    reg = ScriptRegistry(registry_dir)
    for key, title in [
        ("objection_expensive", "Дорого"),
        ("objection_think", "Подумаю"),
        ("objection_competitor", "Конкурент"),
        ("objection_not_interested", "Не цікаво"),
    ]:
        entry = ScriptEntry(key=key, category="objection", title=title)
        entry.add_variant(f"Варіант для {title}", "test")
        reg.save(entry)
    return reg


@pytest.mark.asyncio
async def test_process_call_result_updates_expensive(
    registry_dir: Path, populated_registry: ScriptRegistry
) -> None:
    analyzer = ScriptAnalyzer(registry_dir)
    keys = await analyzer.process_call_result(
        objections=["Це дорого для нас"],
        disposition="successful",
        script_effectiveness="high",
        improvement_suggestions=[],
    )
    assert "objection_expensive" in keys
    loaded = populated_registry.get("objection_expensive")
    assert loaded.variants[0].tested == 1
    assert loaded.variants[0].converted == 1


@pytest.mark.asyncio
async def test_process_call_result_not_converted(
    registry_dir: Path, populated_registry: ScriptRegistry
) -> None:
    analyzer = ScriptAnalyzer(registry_dir)
    keys = await analyzer.process_call_result(
        objections=["подумаю ще"],
        disposition="failed",
        script_effectiveness="medium",
        improvement_suggestions=[],
    )
    assert "objection_think" in keys
    loaded = populated_registry.get("objection_think")
    assert loaded.variants[0].tested == 1
    assert loaded.variants[0].converted == 0


@pytest.mark.asyncio
async def test_process_call_no_matching_objections(
    registry_dir: Path, populated_registry: ScriptRegistry
) -> None:
    analyzer = ScriptAnalyzer(registry_dir)
    keys = await analyzer.process_call_result(
        objections=["нема відповідного заперечення тут"],
        disposition="successful",
        script_effectiveness="high",
        improvement_suggestions=[],
    )
    assert keys == []


@pytest.mark.asyncio
async def test_process_call_multiple_objections(
    registry_dir: Path, populated_registry: ScriptRegistry
) -> None:
    analyzer = ScriptAnalyzer(registry_dir)
    keys = await analyzer.process_call_result(
        objections=["дорого", "є конкурент дешевший"],
        disposition="successful",
        script_effectiveness="high",
        improvement_suggestions=[],
    )
    assert "objection_expensive" in keys
    assert "objection_competitor" in keys


@pytest.mark.asyncio
async def test_process_call_low_effectiveness_proposes_variant(
    registry_dir: Path, populated_registry: ScriptRegistry
) -> None:
    analyzer = ScriptAnalyzer(registry_dir)
    with patch.object(
        analyzer, "_propose_new_variant", new_callable=AsyncMock
    ) as mock_propose:
        await analyzer.process_call_result(
            objections=[],
            disposition="failed",
            script_effectiveness="low",
            improvement_suggestions=["потрібно менше тиснути на клієнта"],
        )
        mock_propose.assert_called_once_with("потрібно менше тиснути на клієнта", "")


@pytest.mark.asyncio
async def test_process_call_empty_objections_list(
    registry_dir: Path, populated_registry: ScriptRegistry
) -> None:
    analyzer = ScriptAnalyzer(registry_dir)
    keys = await analyzer.process_call_result(
        objections=[],
        disposition="successful",
        script_effectiveness="high",
        improvement_suggestions=[],
    )
    assert keys == []
