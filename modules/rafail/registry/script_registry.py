"""ScriptRegistry — реестр скриптів продажів з рейтингами."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ScriptVariant:
    """Один варіант обробки заперечення або скрипт."""

    id: int
    text: str
    source: str = ""
    source_date: str = ""
    tested: int = 0
    converted: int = 0
    status: str = "active"
    notes: str = ""

    @property
    def conversion_rate(self) -> float:
        if self.tested == 0:
            return 0.0
        return round(self.converted / self.tested, 2)

    @property
    def effectiveness(self) -> str:
        rate = self.conversion_rate
        if self.tested < 3:
            return "testing"
        if rate >= 0.6:
            return "high"
        if rate >= 0.3:
            return "medium"
        return "low"


@dataclass
class ScriptEntry:
    """Запис у реєстрі: заперечення або етап розмови."""

    key: str
    category: str
    title: str
    variants: list[ScriptVariant] = field(default_factory=list)
    segment: str = "all"
    updated_at: str = ""

    def best_variant(self) -> ScriptVariant | None:
        active = [v for v in self.variants if v.status == "active"]
        if not active:
            return None
        return max(active, key=lambda v: (v.tested >= 3, v.conversion_rate))

    def add_variant(self, text: str, source: str) -> ScriptVariant:
        new_id = max((v.id for v in self.variants), default=0) + 1
        variant = ScriptVariant(
            id=new_id,
            text=text,
            source=source,
            source_date=datetime.now().strftime("%Y-%m-%d"),
        )
        self.variants.append(variant)
        self.updated_at = datetime.now().isoformat()
        return variant

    def record_result(self, variant_id: int, converted: bool) -> None:
        for v in self.variants:
            if v.id == variant_id:
                v.tested += 1
                if converted:
                    v.converted += 1
                self.updated_at = datetime.now().isoformat()
                break


class ScriptRegistry:
    """Реєстр скриптів продажів."""

    def __init__(self, registry_dir: Path) -> None:
        self._dir = registry_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_entries(self, category: str | None = None) -> list[ScriptEntry]:
        entries = []
        for f in self._dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                entry = self._from_dict(data)
                if category is None or entry.category == category:
                    entries.append(entry)
            except Exception as e:
                logger.warning("[script_registry] помилка читання %s: %s", f, e)
        return entries

    def get(self, key: str) -> ScriptEntry | None:
        path = self._dir / f"{key}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return self._from_dict(data)

    def save(self, entry: ScriptEntry) -> None:
        path = self._dir / f"{entry.key}.yaml"
        path.write_text(
            yaml.dump(self._to_dict(entry), allow_unicode=True), encoding="utf-8"
        )
        logger.info("[script_registry] збережено: %s", entry.key)

    def add_variant(self, key: str, text: str, source: str) -> ScriptVariant | None:
        entry = self.get(key)
        if not entry:
            logger.warning("[script_registry] запис не знайдено: %s", key)
            return None
        variant = entry.add_variant(text, source)
        self.save(entry)
        return variant

    def record_call_result(self, key: str, variant_id: int, converted: bool) -> None:
        entry = self.get(key)
        if not entry:
            return
        entry.record_result(variant_id, converted)
        self.save(entry)

    def get_best_scripts(self, category: str = "objection") -> list[ScriptEntry]:
        entries = self.list_entries(category=category)
        return sorted(
            entries,
            key=lambda e: (e.best_variant().conversion_rate if e.best_variant() else 0),
            reverse=True,
        )

    def _to_dict(self, entry: ScriptEntry) -> dict:
        return {
            "key": entry.key,
            "category": entry.category,
            "title": entry.title,
            "segment": entry.segment,
            "updated_at": entry.updated_at,
            "variants": [
                {
                    "id": v.id,
                    "text": v.text,
                    "source": v.source,
                    "source_date": v.source_date,
                    "tested": v.tested,
                    "converted": v.converted,
                    "status": v.status,
                    "notes": v.notes,
                }
                for v in entry.variants
            ],
        }

    def _from_dict(self, data: dict) -> ScriptEntry:
        variants = [ScriptVariant(**v) for v in data.get("variants", [])]
        return ScriptEntry(
            key=data["key"],
            category=data.get("category", "objection"),
            title=data.get("title", ""),
            segment=data.get("segment", "all"),
            updated_at=data.get("updated_at", ""),
            variants=variants,
        )
