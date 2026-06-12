"""Deep analysis — Gemini. Focus: implementation plan for JARVIS."""
from __future__ import annotations
import logging
from pathlib import Path

from shared import errors
from shared.config import CFG
from shared.llm.providers import gemini as gemini_p
from shared.llm.router import gemini_pool

logger = logging.getLogger(__name__)

DEEP_PROMPT = """Ты архитектор проекта JARVIS (AI-OS: Python 3.11, Electron+React, FastAPI, агенты с BaseAgent, MCP, ChromaDB, Groq/Gemini/Claude API, Telegram-боты, SSH-оркестрация Claude Code).

На основе контента создай план внедрения технологии/идеи в JARVIS. ИГНОРИРУЙ автора и подачу — только техническая интеграция.

**🎯 ЧТО ВНЕДРЯЕМ**
Конкретная технология/паттерн/возможность из контента

**🧩 ИНТЕГРАЦИЯ В JARVIS**
Какой модуль/агент создать или расширить. Как это усиливает Claude/Джарвиса (новые способности агентов, интерфейс, автоматизация)

**📁 ФАЙЛЫ**
Конкретные пути в ~/Projects/jarvis/ для создания/изменения

**💻 КОД**
Минимальный рабочий каркас реализации

**📦 ЗАВИСИМОСТИ**
pip/npm если нужны

**✅ ШАГИ**
Нумерованный план от каркаса до рабочей фичи

**🔗 КЕЙСЫ ПРИМЕНЕНИЯ**
2-3 конкретных сценария где это даёт ценность в JARVIS

Отвечай на русском. Максимально технически конкретно."""


async def deep_analyze(quick_summary: str, image_paths: list[Path], transcripts: list[str]) -> str:
    import PIL.Image
    parts: list = []
    valid = [p for p in image_paths[:16] if p.exists() and p.stat().st_size <= 4 * 1024 * 1024]
    for img_path in valid:
        try:
            parts.append(PIL.Image.open(img_path))
        except Exception as e:
            logger.debug("[DeepPipeline] не удалось открыть изображение %s: %s", img_path, e)
    if transcripts:
        parts.append("Транскрипция/текст:\n" + "\n---\n".join(transcripts))
    if quick_summary:
        parts.append(f"Предварительный анализ:\n{quick_summary[:5000]}")
    parts.append(DEEP_PROMPT)
    if len(parts) == 1:
        return "⚠️ Нет контента для анализа"

    # Анти-шторм: общий пул Gemini + retry_with_backoff (без рекурсии на quota).
    # Модель та же gemini; на 503 — fallback-модель на следующей попытке.
    state = {"fallback": False}

    async def attempt():
        try:
            return await gemini_p.generate(
                CFG.GEMINI_MODEL, parts, gemini_pool,
                fallback_model=CFG.GEMINI_FALLBACK_MODEL,
                max_output_tokens=8192, use_fallback=state["fallback"],
            )
        except Exception as e:
            if errors.classify(e) == "GEMINI_503" and CFG.GEMINI_FALLBACK_MODEL:
                state["fallback"] = True
            raise

    try:
        return await errors.retry_with_backoff(attempt)
    except Exception as e:
        logger.error("[DeepPipeline] code=%s detail=%s", errors.classify(e), e)
        return errors.message_for(e)
