"""Deep analysis — Gemini Pro, максимальные лимиты API."""
from __future__ import annotations
import logging
from pathlib import Path

import config
from pool.api_pool import SimplePool

logger = logging.getLogger(__name__)
_pool = SimplePool(config.GEMINI_KEYS, "gemini")

DEEP_PROMPT = """Сделай детальный план внедрения этого контента в J.A.R.V.I.S. HUD OS.
Стек: MacBook Air M2, Python 3.11, Electron + React, FastAPI, ChromaDB, Groq/Gemini API.

1. ДЕТАЛЬНЫЙ АНАЛИЗ: что показано, технологии, паттерны
2. АРХИТЕКТУРА: какой модуль/агент создать
3. ФАЙЛЫ: конкретные пути в ~/Projects/jarvis/
4. КОД: минимальный рабочий пример
5. ЗАВИСИМОСТИ: pip install / npm install
6. ШАГИ: нумерованный план внедрения

Отвечай на русском. Конкретно и actionable."""

MAX_IMAGES = 16
MAX_SUMMARY = 750_000


def _safe_text(response) -> str:
    try:
        return response.text
    except Exception:
        pass
    try:
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
    except Exception:
        pass
    try:
        reason = response.candidates[0].finish_reason
        reasons = {1: "STOP", 2: "MAX_TOKENS", 3: "SAFETY", 4: "RECITATION", 5: "OTHER"}
        return f"⚠️ Gemini не вернул текст. Причина: {reasons.get(reason, reason)}"
    except Exception:
        return "⚠️ Gemini вернул пустой ответ"


async def deep_analyze(quick_summary: str, image_paths: list[Path], transcripts: list[str]) -> str:
    key = _pool.get()
    if not key:
        return "⚠️ Нет доступных API ключей. Добавьте GEMINI_API_KEY в .env"
    try:
        import google.generativeai as genai
        import PIL.Image
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        parts = []
        valid = [p for p in image_paths[:MAX_IMAGES] if p.exists() and p.stat().st_size <= 4 * 1024 * 1024]
        for img_path in valid:
            try:
                parts.append(PIL.Image.open(img_path))
            except Exception as e:
                logger.warning("Cannot open image %s: %s", img_path, e)
        if transcripts:
            parts.append("Транскрипции:\n" + "\n---\n".join(transcripts))
        if quick_summary:
            parts.append(f"Предварительный анализ:\n{quick_summary[:MAX_SUMMARY]}")
        parts.append(DEEP_PROMPT)

        if len(parts) == 1:
            return "⚠️ Нет медиаконтента для анализа"

        response = await model.generate_content_async(
            parts,
            generation_config={"max_output_tokens": 8192},
        )
        return _safe_text(response)

    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            _pool.report_quota_exceeded(key)
            return await deep_analyze(quick_summary, image_paths, transcripts)
        logger.error("[DeepPipeline] %s", e)
        return f"⚠️ Ошибка: {e}"
