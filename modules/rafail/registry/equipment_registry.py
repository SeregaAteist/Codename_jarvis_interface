"""EquipmentRegistry — реестр оборудования компании."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ServiceInterval:
    months: int
    action: str


@dataclass
class EquipmentCard:
    model: str
    brand: str
    category: str
    price_current: float = 0.0
    documents: list[str] = field(default_factory=list)
    service_intervals: list[ServiceInterval] = field(default_factory=list)
    compatible_with: list[str] = field(default_factory=list)
    courses_linked: list[str] = field(default_factory=list)
    specs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> EquipmentCard:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        intervals = [ServiceInterval(**i) for i in data.pop("service_intervals", [])]
        return cls(
            **{k: data[k] for k in cls.__dataclass_fields__ if k in data},
            service_intervals=intervals,
        )

    def to_yaml(self) -> str:
        data: dict[str, Any] = {
            "model": self.model,
            "brand": self.brand,
            "category": self.category,
            "price_current": self.price_current,
            "documents": self.documents,
            "service_intervals": [
                {"months": i.months, "action": i.action} for i in self.service_intervals
            ],
            "compatible_with": self.compatible_with,
            "courses_linked": self.courses_linked,
            "specs": self.specs,
        }
        result: str = yaml.dump(data, allow_unicode=True)
        return result


class EquipmentRegistry:
    """Реестр оборудования компании."""

    def __init__(self, equipment_dir: Path) -> None:
        self._dir = equipment_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_brands(self) -> list[str]:
        return [d.name for d in self._dir.iterdir() if d.is_dir()]

    def list_models(self, brand: str | None = None) -> list[EquipmentCard]:
        cards = []
        dirs = [self._dir / brand] if brand else list(self._dir.iterdir())
        for d in dirs:
            if not d.is_dir():
                continue
            for f in d.glob("*.yaml"):
                try:
                    cards.append(EquipmentCard.from_yaml(f))
                except Exception as e:
                    logger.warning("[registry] ошибка чтения %s: %s", f, e)
        return cards

    def get(self, brand: str, model_slug: str) -> EquipmentCard | None:
        path = self._dir / brand / f"{model_slug}.yaml"
        if not path.exists():
            return None
        return EquipmentCard.from_yaml(path)

    def save(self, card: EquipmentCard) -> Path:
        brand_dir = self._dir / card.brand.lower().replace(" ", "_")
        brand_dir.mkdir(exist_ok=True)
        slug = card.model.lower().replace(" ", "_")
        path = brand_dir / f"{slug}.yaml"
        path.write_text(card.to_yaml(), encoding="utf-8")
        logger.info("[registry] сохранено: %s / %s", card.brand, card.model)
        return path

    def search(self, query: str) -> list[EquipmentCard]:
        query_lower = query.lower()
        return [
            card
            for card in self.list_models()
            if query_lower in card.model.lower() or query_lower in card.brand.lower()
        ]
