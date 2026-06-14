"""Unit-тесты для ScriptRegistry."""

import pytest

from modules.rafail.registry.script_registry import (
    ScriptEntry,
    ScriptRegistry,
    ScriptVariant,
)


@pytest.fixture
def registry(tmp_path):
    return ScriptRegistry(tmp_path)


def test_save_and_get(registry):
    entry = ScriptEntry(key="test_key", category="objection", title="Тест")
    entry.add_variant("текст варіанту", "тест")
    registry.save(entry)
    loaded = registry.get("test_key")
    assert loaded is not None
    assert loaded.title == "Тест"
    assert len(loaded.variants) == 1


def test_get_missing_returns_none(registry):
    assert registry.get("nonexistent") is None


def test_conversion_rate():
    v = ScriptVariant(id=1, text="test", tested=10, converted=7)
    assert v.conversion_rate == 0.7


def test_conversion_rate_zero_tested():
    v = ScriptVariant(id=1, text="test", tested=0, converted=0)
    assert v.conversion_rate == 0.0


def test_effectiveness_high():
    v = ScriptVariant(id=1, text="test", tested=5, converted=4)
    assert v.effectiveness == "high"


def test_effectiveness_medium():
    v = ScriptVariant(id=1, text="test", tested=5, converted=2)
    assert v.effectiveness == "medium"


def test_effectiveness_low():
    v = ScriptVariant(id=1, text="test", tested=5, converted=1)
    assert v.effectiveness == "low"


def test_effectiveness_testing():
    v = ScriptVariant(id=1, text="test", tested=2, converted=1)
    assert v.effectiveness == "testing"


def test_best_variant_prefers_higher_conversion(registry):
    entry = ScriptEntry(key="test", category="objection", title="Тест")
    entry.add_variant("варіант 1", "test")
    entry.variants[0].tested = 5
    entry.variants[0].converted = 4
    entry.add_variant("варіант 2", "test")
    entry.variants[1].tested = 5
    entry.variants[1].converted = 2
    best = entry.best_variant()
    assert best is not None
    assert best.id == 1


def test_best_variant_tested_beats_untested(registry):
    entry = ScriptEntry(key="test", category="objection", title="Тест")
    entry.add_variant("варіант 1", "test")
    entry.variants[0].tested = 0
    entry.add_variant("варіант 2", "test")
    entry.variants[1].tested = 5
    entry.variants[1].converted = 2
    best = entry.best_variant()
    assert best is not None
    assert best.id == 2


def test_best_variant_empty_returns_none():
    entry = ScriptEntry(key="empty", category="objection", title="Порожній")
    assert entry.best_variant() is None


def test_best_variant_skips_archived():
    entry = ScriptEntry(key="test", category="objection", title="Тест")
    entry.add_variant("варіант archived", "test")
    entry.variants[0].status = "archived"
    entry.variants[0].tested = 10
    entry.variants[0].converted = 9
    assert entry.best_variant() is None


def test_record_result(registry):
    entry = ScriptEntry(key="test2", category="objection", title="Тест 2")
    entry.add_variant("варіант", "test")
    registry.save(entry)
    registry.record_call_result("test2", 1, converted=True)
    loaded = registry.get("test2")
    assert loaded.variants[0].tested == 1
    assert loaded.variants[0].converted == 1


def test_record_result_not_converted(registry):
    entry = ScriptEntry(key="test3", category="objection", title="Тест 3")
    entry.add_variant("варіант", "test")
    registry.save(entry)
    registry.record_call_result("test3", 1, converted=False)
    loaded = registry.get("test3")
    assert loaded.variants[0].tested == 1
    assert loaded.variants[0].converted == 0


def test_add_variant(registry):
    entry = ScriptEntry(key="addtest", category="objection", title="Тест")
    entry.add_variant("перший", "test")
    registry.save(entry)
    v = registry.add_variant("addtest", "другий", "test2")
    assert v is not None
    assert v.id == 2
    loaded = registry.get("addtest")
    assert len(loaded.variants) == 2


def test_add_variant_missing_key(registry):
    result = registry.add_variant("nonexistent", "текст", "src")
    assert result is None


def test_list_entries_by_category(registry):
    e1 = ScriptEntry(key="obj1", category="objection", title="О1")
    e2 = ScriptEntry(key="stg1", category="stage", title="С1")
    registry.save(e1)
    registry.save(e2)
    objections = registry.list_entries(category="objection")
    assert len(objections) == 1
    assert objections[0].key == "obj1"


def test_get_best_scripts_sorted(registry):
    e1 = ScriptEntry(key="obj_a", category="objection", title="А")
    e1.add_variant("текст", "test")
    e1.variants[0].tested = 5
    e1.variants[0].converted = 1
    e2 = ScriptEntry(key="obj_b", category="objection", title="Б")
    e2.add_variant("текст", "test")
    e2.variants[0].tested = 5
    e2.variants[0].converted = 4
    registry.save(e1)
    registry.save(e2)
    best = registry.get_best_scripts(category="objection")
    assert best[0].key == "obj_b"
