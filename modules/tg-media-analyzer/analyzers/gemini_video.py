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
        import google.generativeai as genai
        genai.configure(api_key=key)

        # Загрузка видео через File API (блокирующая — в отдельном потоке)
        uploaded = await asyncio.to_thread(genai.upload_file, path=str(video_path))

        # Ждём пока файл обработается (ACTIVE)
        for _ in range(60):
            f = await asyncio.to_thread(genai.get_file, uploaded.name)
            if f.state.name == "ACTIVE":
                break
            if f.state.name == "FAILED":
                return "⚠️ Gemini не смог обработать видео"
            await asyncio.sleep(2)
        else:
            return "⚠️ Таймаут обработки видео Gemini"

        model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        )
        response = await model.generate_content_async(
            [uploaded, prompt],
            generation_config={"max_output_tokens": 8192},
        )

        # Удалить файл с серверов Gemini
        try:
            await asyncio.to_thread(genai.delete_file, uploaded.name)
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
