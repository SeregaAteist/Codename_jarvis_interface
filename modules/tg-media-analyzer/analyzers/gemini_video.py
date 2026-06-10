"""Gemini native video analysis — uploads full video, transcribes + analyzes audio+visual."""
from __future__ import annotations
import asyncio
import logging
import time
from pathlib import Path

import config

logger = logging.getLogger(__name__)


async def analyze_video_native(video_path: Path, prompt: str, pool) -> str:
    """Upload video to Gemini File API, analyze audio+visual in one pass."""
    key = pool.get()
    if not key:
        return "⚠️ Gemini недоступен — нет ключей"
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)

        # Загрузка видео через File API (нативный async в новом SDK)
        uploaded = await client.aio.files.upload(file=str(video_path))

        # Ждём пока файл обработается (ACTIVE)
        for _ in range(60):
            f = await client.aio.files.get(name=uploaded.name)
            if f.state.name == "ACTIVE":
                break
            if f.state.name == "FAILED":
                return "⚠️ Gemini не смог обработать видео"
            await asyncio.sleep(2)
        else:
            return "⚠️ Таймаут обработки видео Gemini"

        safety = [
            types.SafetySetting(category=c, threshold="BLOCK_NONE")
            for c in ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
        ]
        response = await client.aio.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[uploaded, prompt],
            config=types.GenerateContentConfig(safety_settings=safety, max_output_tokens=8192),
        )

        # Удалить файл с серверов Gemini
        try:
            await client.aio.files.delete(name=uploaded.name)
        except Exception:
            pass

        try:
            return response.text
        except Exception:
            for c in response.candidates:
                for p in c.content.parts:
                    if getattr(p, "text", ""):
                        return p.text
            return "⚠️ Gemini не вернул текст"

    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            pool.report_quota_exceeded(key)
            return await analyze_video_native(video_path, prompt, pool)
        logger.error("[GeminiVideo] %s", e)
        return f"⚠️ Ошибка: {e}"
