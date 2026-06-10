"""Photo analyzer — uses Gemini for quick analysis."""
from __future__ import annotations
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def analyze_photos(image_paths: list[Path], pool) -> str:
    key = pool.get()
    if not key:
        return "⚠️ Gemini недоступен"
    try:
        from google import genai
        import PIL.Image
        client = genai.Client(api_key=key)
        parts = []
        for img in image_paths[:8]:
            try:
                parts.append(PIL.Image.open(img))
            except Exception as e:
                logger.warning("Cannot open image %s: %s", img, e)
        parts.append(
            "Проанализируй изображения. Что показано? Какие UI/UX паттерны, технологии, идеи? "
            "Как это можно применить в AI-ассистенте (JARVIS)? Отвечай на русском, кратко и конкретно."
        )
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash", contents=parts,
        )
        pool._idx  # touch to register usage
        return response.text
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            pool.report_quota_exceeded(key)
            return await analyze_photos(image_paths, pool)
        logger.error("[PhotoAnalyzer] %s", e)
        return f"⚠️ Ошибка: {e}"
