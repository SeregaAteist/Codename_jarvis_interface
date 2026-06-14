"""ScriptExtractor — витягує скрипти з навчальних матеріалів."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from shared.llm.router import get_router

logger = logging.getLogger(__name__)


class ScriptExtractor:
    """Сканує навчальний контент і витягує скрипти продажів."""

    def __init__(self, registry_dir: Path) -> None:
        from modules.rafail.registry.script_registry import ScriptRegistry

        self._registry = ScriptRegistry(registry_dir)
        self._router = get_router()

    async def scan(self, content: str, source: str = "") -> list[str]:
        """Сканувати контент на скрипти і техніки продажів.

        Повертає список ключів оновлених записів.
        """
        if not content or len(content) < 100:
            return []

        prompt = f"""Проаналізуй навчальний матеріал з продажів і витягни скрипти та техніки.

Матеріал:
{content[:6000]}

Знайди:
1. Варіанти обробки заперечень (дорого, подумаю, є конкурент, не цікаво)
2. Техніки відкриття/закриття розмови
3. Питання для виявлення потреб

Поверни JSON масив:
[
  {{
    "key": "objection_expensive",
    "category": "objection",
    "title": "Заперечення: дорого",
    "variant_text": "текст скрипту...",
    "source": "{source}"
  }}
]

Якщо скриптів немає — поверни порожній масив [].
Тільки JSON."""

        raw = await self._router.generate("quality", prompt)

        try:
            text = raw.strip().strip("```json").strip("```").strip()
            if text == "[]":
                return []
            items = json.loads(text)
        except Exception as e:
            logger.error("[extractor] JSON parse error: %s", e)
            return []

        updated_keys: list[str] = []
        for item in items:
            key = item.get("key", "")
            if not key:
                continue

            entry = self._registry.get(key)
            if entry:
                variant = self._registry.add_variant(
                    key=key,
                    text=item.get("variant_text", ""),
                    source=source,
                )
                if variant:
                    logger.info("[extractor] новий варіант для %s з '%s'", key, source)
                    updated_keys.append(key)
            else:
                from modules.rafail.registry.script_registry import ScriptEntry

                new_entry = ScriptEntry(
                    key=key,
                    category=item.get("category", "objection"),
                    title=item.get("title", key),
                )
                new_entry.add_variant(
                    text=item.get("variant_text", ""),
                    source=source,
                )
                self._registry.save(new_entry)
                logger.info("[extractor] новий запис %s з '%s'", key, source)
                updated_keys.append(key)

        return updated_keys
