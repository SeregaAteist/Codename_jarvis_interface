"""Quick analysis — через единый LLM-роутер (роль quick_analysis → gemini)."""

from __future__ import annotations

import logging
from pathlib import Path

from shared.llm import router
from shared.llm.router import (
    gemini_pool as _gemini_pool,
)  # re-export: handlers/video import this

__all__ = ["_gemini_pool", "QUICK_PROMPT", "quick_analyze"]

logger = logging.getLogger(__name__)

QUICK_PROMPT = """Ты технический аналитик проекта JARVIS (AI-OS платформа: Python, Electron, React, FastAPI, агенты, MCP, Claude/Gemini API).

Проанализируй контент и извлеки ТЕХНИЧЕСКУЮ суть. ИГНОРИРУЙ внешность автора, его личность, манеру подачи — только технологии и идеи.

Формат:
**⚙️ Технология/инструмент:** что конкретно показано (фреймворк, библиотека, паттерн, API, сервис)
**🧩 Применимость к JARVIS/Claude:** как это усиливает агентов, интерфейс или возможности — конкретно
**🔑 Ключевой приём:** главный технический трюк/решение из контента
**📊 Оценка:** внедрять / изучить / пропустить — почему

Отвечай на русском. Только техническая ценность. Без воды."""


async def quick_analyze(
    image_paths: list[Path],
    transcripts: list[str],
    *,
    on_progress=None,
    deadline_ts=None,
) -> str:
    parts: list = []
    for img_path in image_paths[:8]:
        if img_path.exists():
            try:
                import PIL.Image

                parts.append(PIL.Image.open(img_path))
            except Exception:
                pass
    if transcripts:
        parts.append("Транскрипция/текст из видео:\n" + "\n---\n".join(transcripts))
    parts.append(QUICK_PROMPT)
    try:
        return await router.generate(
            "quick_analysis", parts, on_progress=on_progress, deadline_ts=deadline_ts
        )
    except Exception as e:
        from shared.errors import classify, message_for

        logger.error("[QuickPipeline] code=%s detail=%s", classify(e), e)
        return message_for(e)  # короткое сообщение из карты, без сырого JSON
