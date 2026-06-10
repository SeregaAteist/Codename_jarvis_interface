"""Deep analysis — Gemini. Focus: implementation plan for JARVIS."""
from __future__ import annotations
import logging
from pathlib import Path

import config
from pool.api_pool import SimplePool

logger = logging.getLogger(__name__)
_pool = SimplePool(config.GEMINI_KEYS, "gemini")

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
    key = _pool.get()
    if not key:
        return "⚠️ Нет API ключей — добавьте GEMINI_API_KEY в .env"
    try:
        import google.generativeai as genai
        import PIL.Image
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        )
        parts = []
        valid = [p for p in image_paths[:16] if p.exists() and p.stat().st_size <= 4 * 1024 * 1024]
        for img_path in valid:
            try:
                parts.append(PIL.Image.open(img_path))
            except Exception:
                pass
        if transcripts:
            parts.append("Транскрипция/текст:\n" + "\n---\n".join(transcripts))
        if quick_summary:
            parts.append(f"Предварительный анализ:\n{quick_summary[:5000]}")
        parts.append(DEEP_PROMPT)
        if len(parts) == 1:
            return "⚠️ Нет контента для анализа"
        response = await model.generate_content_async(
            parts, generation_config={"max_output_tokens": 8192}
        )
        try:
            return response.text
        except Exception:
            for c in response.candidates:
                for p in c.content.parts:
                    if getattr(p, "text", ""):
                        return p.text
            reason = response.candidates[0].finish_reason if response.candidates else "?"
            return f"⚠️ Gemini не вернул текст (finish_reason={reason})"
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            _pool.report_quota_exceeded(key)
            return await deep_analyze(quick_summary, image_paths, transcripts)
        logger.error("[DeepPipeline] %s", e)
        return f"⚠️ Ошибка: {e}"
