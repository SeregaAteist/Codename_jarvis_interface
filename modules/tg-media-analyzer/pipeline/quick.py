"""Quick analysis — Gemini Flash. Focus: tech extraction, not author."""
from __future__ import annotations
import logging
from pathlib import Path

import config
from pool.api_pool import SimplePool

logger = logging.getLogger(__name__)
_gemini_pool = SimplePool(config.GEMINI_KEYS, "gemini")

QUICK_PROMPT = """Ты технический аналитик проекта JARVIS (AI-OS платформа: Python, Electron, React, FastAPI, агенты, MCP, Claude/Gemini API).

Проанализируй контент и извлеки ТЕХНИЧЕСКУЮ суть. ИГНОРИРУЙ внешность автора, его личность, манеру подачи — только технологии и идеи.

Формат:
**⚙️ Технология/инструмент:** что конкретно показано (фреймворк, библиотека, паттерн, API, сервис)
**🧩 Применимость к JARVIS/Claude:** как это усиливает агентов, интерфейс или возможности — конкретно
**🔑 Ключевой приём:** главный технический трюк/решение из контента
**📊 Оценка:** внедрять / изучить / пропустить — почему

Отвечай на русском. Только техническая ценность. Без воды."""


async def quick_analyze(image_paths: list[Path], transcripts: list[str]) -> str:
    key = _gemini_pool.get()
    if not key:
        return "⚠️ Gemini недоступен — добавьте GEMINI_API_KEY в .env"
    try:
        from google import genai
        from google.genai import types
        import PIL.Image
        client = genai.Client(api_key=key)
        safety = [
            types.SafetySetting(category=c, threshold="BLOCK_NONE")
            for c in ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
        ]
        parts = []
        for img_path in image_paths[:8]:
            if img_path.exists():
                try:
                    parts.append(PIL.Image.open(img_path))
                except Exception:
                    pass
        if transcripts:
            parts.append("Транскрипция/текст из видео:\n" + "\n---\n".join(transcripts))
        parts.append(QUICK_PROMPT)
        response = await client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(safety_settings=safety),
        )
        try:
            return response.text
        except Exception:
            for c in response.candidates:
                for p in c.content.parts:
                    if getattr(p, "text", ""):
                        return p.text
            return "⚠️ Gemini не вернул текст (safety/empty)"
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            _gemini_pool.report_quota_exceeded(key)
            return await quick_analyze(image_paths, transcripts)
        logger.error("[QuickPipeline] %s", e)
        return f"⚠️ Ошибка Gemini: {e}"
