"""Quick analysis — Gemini Flash, free tier, fast."""
from __future__ import annotations
import logging
from pathlib import Path

import config
from pool.api_pool import SimplePool

logger = logging.getLogger(__name__)

_gemini_pool = SimplePool(config.GEMINI_KEYS, "gemini")

QUICK_PROMPT = """Проанализируй этот медиаконтент для AI-ассистента JARVIS.

**🔍 Что показано:** (1-2 предложения)
**💡 Ключевая идея:** (1 предложение)
**🚀 Применимость в JARVIS:** высокая / средняя / низкая — почему
**⚡ Вывод:** (1 actionable предложение)

Отвечай на русском. Кратко и конкретно."""


async def quick_analyze(image_paths: list[Path], transcripts: list[str]) -> str:
    key = _gemini_pool.get()
    if not key:
        return "⚠️ Gemini недоступен — добавьте GEMINI_API_KEY в .env"
    try:
        import google.generativeai as genai
        import PIL.Image
        genai.configure(api_key=key)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        parts = []
        for img_path in image_paths[:6]:
            try:
                parts.append(PIL.Image.open(img_path))
            except Exception:
                pass
        if transcripts:
            parts.append("Транскрипция видео/аудио:\n" + "\n---\n".join(transcripts))
        parts.append(QUICK_PROMPT)
        response = await model.generate_content_async(parts)
        return response.text
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            _gemini_pool.report_quota_exceeded(key)
            return await quick_analyze(image_paths, transcripts)
        logger.error("[QuickPipeline] %s", e)
        return f"⚠️ Ошибка Gemini: {e}"
