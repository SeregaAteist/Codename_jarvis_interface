"""PriceParser — парсинг прайс-листов Excel/PDF → реестр оборудования."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

KNOWN_BRANDS = [
    "Deye",
    "Pylontech",
    "JA Solar",
    "LONGi",
    "Huawei",
    "Solis",
    "Growatt",
    "Sofar",
    "Goodwe",
    "SMA",
    "Victron",
    "Fronius",
    "ABB",
    "Schneider",
]

CATEGORIES = {
    "inverter": ["інвертор", "inverter", "перетворювач"],
    "panel": ["панель", "panel", "модуль", "module", "pv"],
    "battery": ["акумулятор", "battery", "АКБ", "накопичувач", "pylontech"],
    "cable": ["кабель", "cable", "провід"],
    "switch": ["вимикач", "щит", "автомат", "switch"],
}


@dataclass
class PriceItem:
    name: str
    brand: str = ""
    model: str = ""
    category: str = ""
    price: float = 0.0
    currency: str = "UAH"
    unit: str = "шт"
    specs: dict[str, Any] = field(default_factory=dict)

    def detect_brand(self) -> None:
        for brand in KNOWN_BRANDS:
            if brand.lower() in self.name.lower():
                self.brand = brand
                self.model = self.name.replace(brand, "").strip()
                break

    def detect_category(self) -> None:
        name_lower = self.name.lower()
        for cat, keywords in CATEGORIES.items():
            if any(kw in name_lower for kw in keywords):
                self.category = cat
                return
        self.category = "other"


class PriceParser:
    """Парсит прайс-листы Excel/PDF и извлекает позиции оборудования."""

    async def parse_excel(self, path: Path) -> list[PriceItem]:
        """Парсить Excel прайс."""
        try:
            import openpyxl

            wb = openpyxl.load_workbook(path, data_only=True)
            items = []
            for sheet in wb.worksheets:
                items.extend(self._parse_sheet(sheet))
            return items
        except Exception as e:
            logger.error("[price_parser] Excel %s: %s", path, e)
            return []

    def _parse_sheet(self, sheet: Any) -> list[PriceItem]:
        items = []
        for row in sheet.iter_rows(values_only=True):
            if not row or not row[0]:
                continue
            name = str(row[0]).strip()
            if len(name) < 3:
                continue

            # ищем цену в строке
            price = 0.0
            for cell in row[1:]:
                if cell and isinstance(cell, (int, float)) and cell > 0:
                    price = float(cell)
                    break

            item = PriceItem(name=name, price=price)
            item.detect_brand()
            item.detect_category()
            items.append(item)
        return items

    async def parse_url(self, url: str) -> list[PriceItem]:
        """Скачать и парсить прайс по URL."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(url)
            r.raise_for_status()

        suffix = ".xlsx" if "excel" in r.headers.get("content-type", "") else ".xlsx"
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(r.content)
            tmp = Path(f.name)

        try:
            return await self.parse_excel(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    async def parse_with_gemini(self, path: Path) -> list[PriceItem]:
        """Парсить прайс через Gemini если стандартный парсер не справился."""
        from modules.rafail.researchers.doc_parser import DocParser
        from shared.llm.router import get_router

        parser = DocParser()
        text = await parser.parse_file(path)

        router = get_router()
        schema = (
            '[{"name": "...", "brand": "...", "model": "...", '
            '"category": "inverter/panel/battery/cable/other", '
            '"price": 0.0, "currency": "UAH"}]'
        )
        prompt = (
            "Витягни з прайс-листу всі позиції обладнання для СЕС.\n\n"
            f"Прайс:\n{text[:8000]}\n\n"
            f"Верни JSON масив:\n{schema}\n\n"
            "Тільки JSON, без пояснень."
        )

        raw = await router.generate("quality", prompt)

        import json

        try:
            text_clean = raw.strip().strip("```json").strip("```").strip()
            data = json.loads(text_clean)
            items = []
            for d in data:
                item = PriceItem(
                    **{k: d[k] for k in PriceItem.__dataclass_fields__ if k in d}
                )
                items.append(item)
            return items
        except Exception as e:
            logger.error("[price_parser] Gemini JSON: %s", e)
            return []

    def to_equipment_cards(self, items: list[PriceItem]) -> list[Any]:
        """Конвертировать позиции прайса в карточки оборудования."""
        from modules.rafail.registry.equipment_registry import EquipmentCard

        cards: list[Any] = []
        for item in items:
            if not item.brand or item.category == "other":
                continue
            card = EquipmentCard(
                model=item.model or item.name,
                brand=item.brand,
                category=item.category,
                price_current=item.price,
            )
            cards.append(card)
        return cards
