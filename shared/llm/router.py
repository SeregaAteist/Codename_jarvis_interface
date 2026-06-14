"""Единый LLM-роутер: task_type → провайдер/модель (из config.yaml секция llm.roles).

generate(task_type, content) находит роль в конфиге ("provider/model"),
вызывает нужный провайдер. Пул ключей Gemini общий (key_pool), ротация —
через сам пул + логику провайдера.
"""

from __future__ import annotations

import logging
from typing import Any

from shared import errors
from shared.config import CFG
from shared.llm.key_pool import SimplePool
from shared.llm.providers import anthropic as anthropic_p
from shared.llm.providers import gemini as gemini_p
from shared.llm.providers import groq as groq_p
from shared.llm.providers import ollama as ollama_p

logger = logging.getLogger(__name__)

# Общий пул ключей Gemini. Экспортируется модульно — ряд модулей импортирует напрямую.
gemini_pool = SimplePool(CFG.GEMINI_KEYS, "gemini")

_DEFAULT_ROLES: dict[str, str] = {
    "quick_analysis": f"gemini/{CFG.GEMINI_MODEL}",
    "architect": f"claude/{CFG.CLAUDE_MODEL}",
    "local_chat": f"ollama/{CFG.OLLAMA_MODEL}",
    "recommend": "groq/llama-3.3-70b-versatile",
}


class LLMRouter:
    """Единая точка доступа к LLM провайдерам.

    Пример использования:
        router = get_router()
        answer = await router.generate("quality", "Поясни переваги СЕС")
        summary = await router.generate("speed", "Стисни текст: {text}")
    """

    def __init__(self) -> None:
        self._gemini_pool = gemini_pool

    def _roles(self) -> dict[str, str]:
        return {**_DEFAULT_ROLES, **(CFG.raw.get("llm", {}).get("roles", {}) or {})}

    def resolve(self, task_type: str) -> tuple[str, str]:
        """task_type → (provider, model)."""
        role = self._roles().get(task_type)
        if not role or "/" not in role:
            raise ValueError(
                f"Неизвестная роль '{task_type}'. Доступны: {sorted(self._roles())}"
            )
        provider, model = role.split("/", 1)
        return provider, model

    async def generate(
        self,
        task_type: str,
        content: Any,
        *,
        on_progress: Any = None,
        deadline_ts: float | None = None,
    ) -> str:
        """Сгенерировать ответ для роли task_type.

        content зависит от провайдера (gemini: список частей PIL/строк; text-провайдеры: строка).
        on_progress(text) — статус повторов в чат; deadline_ts — глобальный дедлайн.
        """
        provider, model = self.resolve(task_type)
        if provider == "gemini":
            state: dict[str, bool] = {"fallback": False}

            async def attempt() -> str:
                try:
                    return await gemini_p.generate(
                        model,
                        content,
                        self._gemini_pool,
                        fallback_model=CFG.GEMINI_FALLBACK_MODEL,
                        use_fallback=state["fallback"],
                    )
                except Exception as e:
                    if errors.classify(e) == "GEMINI_503" and CFG.GEMINI_FALLBACK_MODEL:
                        state["fallback"] = True
                    raise

            return await errors.retry_with_backoff(
                attempt, on_progress=on_progress, deadline_ts=deadline_ts
            )
        if provider == "claude":
            return await anthropic_p.generate(model, content)
        if provider == "ollama":
            return await ollama_p.generate(model, content)
        if provider == "groq":
            return await groq_p.generate(model, content)
        raise ValueError(f"Неизвестный провайдер '{provider}' для роли '{task_type}'")


# синглтон
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


# backward compat — модульные функции
def resolve(task_type: str) -> tuple[str, str]:
    return get_router().resolve(task_type)


async def generate(
    task_type: str,
    content: Any,
    *,
    on_progress: Any = None,
    deadline_ts: float | None = None,
) -> str:
    return await get_router().generate(
        task_type, content, on_progress=on_progress, deadline_ts=deadline_ts
    )
