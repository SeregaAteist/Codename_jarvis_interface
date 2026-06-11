"""Единый LLM-роутер: task_type → провайдер/модель (из config.yaml секция llm.roles).

generate(task_type, content) находит роль в конфиге ("provider/model"),
вызывает нужный провайдер. Пул ключей Gemini общий (key_pool), ротация —
через сам пул + логику провайдера.
"""
from __future__ import annotations

import logging

from shared.config import CFG
from shared.llm.key_pool import SimplePool
from shared.llm.providers import anthropic as anthropic_p
from shared.llm.providers import gemini as gemini_p
from shared.llm.providers import groq as groq_p
from shared.llm.providers import ollama as ollama_p

logger = logging.getLogger(__name__)

# Общий пул ключей Gemini (round-robin + cooldown).
gemini_pool = SimplePool(CFG.GEMINI_KEYS, "gemini")

# Дефолтная карта ролей, если в yaml секции нет.
_DEFAULT_ROLES = {
    "quick_analysis": f"gemini/{CFG.GEMINI_MODEL}",
    "architect": f"claude/{CFG.CLAUDE_MODEL}",
    "local_chat": f"ollama/{CFG.OLLAMA_MODEL}",
    "recommend": "groq/llama-3.3-70b-versatile",
}


def _roles() -> dict:
    return {**_DEFAULT_ROLES, **(CFG.raw.get("llm", {}).get("roles", {}) or {})}


def resolve(task_type: str) -> tuple[str, str]:
    """task_type → (provider, model)."""
    role = _roles().get(task_type)
    if not role or "/" not in role:
        raise ValueError(f"Неизвестная роль '{task_type}'. Доступны: {sorted(_roles())}")
    provider, model = role.split("/", 1)
    return provider, model


async def generate(task_type: str, content) -> str:
    """Сгенерировать ответ для роли task_type. content зависит от провайдера
    (gemini: список частей PIL/строк; text-провайдеры: строка)."""
    provider, model = resolve(task_type)
    if provider == "gemini":
        return await gemini_p.generate(
            model, content, gemini_pool, fallback_model=CFG.GEMINI_FALLBACK_MODEL
        )
    if provider == "claude":
        return await anthropic_p.generate(model, content)
    if provider == "ollama":
        return await ollama_p.generate(model, content)
    if provider == "groq":
        return await groq_p.generate(model, content)
    raise ValueError(f"Неизвестный провайдер '{provider}' для роли '{task_type}'")
