"""ScriptAnalyzer — аналізує результати дзвінків і оновлює рейтинги скриптів."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_OBJECTION_MAP = {
    "дорого": "objection_expensive",
    "дорогий": "objection_expensive",
    "дорога": "objection_expensive",
    "подумаю": "objection_think",
    "подумать": "objection_think",
    "конкурент": "objection_competitor",
    "інша пропозиція": "objection_competitor",
    "не цікаво": "objection_not_interested",
    "не интересно": "objection_not_interested",
}


class ScriptAnalyzer:
    """Зв'язує результати дзвінків з реєстром скриптів."""

    def __init__(self, registry_dir: Path) -> None:
        from modules.rafail.registry.script_registry import ScriptRegistry

        self._registry = ScriptRegistry(registry_dir)

    async def process_call_result(
        self,
        objections: list[str],
        disposition: str,
        script_effectiveness: str,
        improvement_suggestions: list[str],
        source: str = "",
    ) -> list[str]:
        """Оновити рейтинги скриптів на основі результату дзвінка."""
        updated: list[str] = []
        converted = disposition == "successful"

        for objection in objections:
            obj_lower = objection.lower()
            for keyword, key in _OBJECTION_MAP.items():
                if keyword in obj_lower:
                    entry = self._registry.get(key)
                    if entry and entry.best_variant():
                        self._registry.record_call_result(
                            key=key,
                            variant_id=entry.best_variant().id,
                            converted=converted,
                        )
                        updated.append(key)
                    break

        if script_effectiveness == "low" and improvement_suggestions:
            for suggestion in improvement_suggestions:
                await self._propose_new_variant(suggestion, source)

        return updated

    async def _propose_new_variant(self, suggestion: str, source: str) -> None:
        from shared.llm.router import get_router

        router = get_router()

        script_text = await router.generate(
            "quality",
            f"На основі рекомендації склади конкретний скрипт для менеджера з продажу СЕС.\n\n"
            f"Рекомендація: {suggestion}\n\n"
            f"Поверни ТІЛЬКИ текст скрипту (1-3 речення) без пояснень.",
        )

        key_raw = await router.generate(
            "filter",
            f"До якого заперечення відноситься цей скрипт?\n{script_text}\n\n"
            f"Поверни ОДИН ключ: objection_expensive / objection_think / "
            f"objection_competitor / objection_not_interested / opening / closing / other",
        )
        key = key_raw.strip().lower()

        if key != "other" and self._registry.get(key):
            self._registry.add_variant(
                key=key,
                text=script_text.strip(),
                source=f"авто: {source}",
            )
            logger.info("[script_analyzer] запропоновано новий варіант для %s", key)
