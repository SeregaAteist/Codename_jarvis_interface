"""Gemini native video analysis — загрузка видео в File API, разбор аудио+видео.

Отказоустойчивость (Фаза 5):
- F-1: прогресс-стадии (Загружаю → Google обрабатывает → Анализирую).
- F-6 анти-шторм: видео грузится ОДИН раз; повторяется только generate (переиспользуем
  File URI), а не upload. 429 → заморозка ключа (пул), без повторов. retry для 503/500/NET.
- Глобальный дедлайн (deadline_ts) и карта ошибок — общие (shared/errors).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import config

from shared.errors import QuotaExhausted, classify, message_for, retry_with_backoff

logger = logging.getLogger(__name__)

_SAFETY_CATS = (
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
)


def _text(response) -> str:
    try:
        return response.text
    except Exception:
        for c in getattr(response, "candidates", []) or []:
            for p in c.content.parts:
                if getattr(p, "text", ""):
                    return p.text
        raise RuntimeError("EMPTY: Gemini вернул пустой ответ по видео")


async def _emit(on_progress, text: str) -> None:
    if on_progress:
        try:
            await on_progress(text)
        except Exception:
            pass


async def analyze_video_native(
    video_path: Path, prompt: str, pool, *, on_progress=None, deadline_ts=None
) -> str:
    from google import genai
    from google.genai import types

    key = pool.get()
    if not key:
        return message_for(QuotaExhausted("нет доступных ключей Gemini"))
    client = genai.Client(api_key=key)

    # --- F-1: загрузка (один раз) ---
    await _emit(on_progress, "📤 Загружаю видео в Gemini…")
    try:
        uploaded = await client.aio.files.upload(file=str(video_path))
    except Exception as e:
        if classify(e) == "GEMINI_429":
            pool.report_quota_exceeded(key)
        logger.error("[GeminiVideo] upload code=%s detail=%s", classify(e), e)
        return message_for(e)

    # --- F-1: ждём ACTIVE (Google обрабатывает) ---
    await _emit(on_progress, "⏳ Google обрабатывает видео…")
    try:
        for _ in range(60):
            f = await client.aio.files.get(name=uploaded.name)
            if f.state.name == "ACTIVE":
                break
            if f.state.name == "FAILED":
                return message_for(
                    RuntimeError("MEDIA: Gemini не смог обработать видео")
                )
            await asyncio.sleep(2)
        else:
            return message_for(RuntimeError("MEDIA: таймаут обработки видео Gemini"))

        # --- анализ: upload НЕ повторяем, retry только generate (reuse URI) ---
        await _emit(on_progress, "🔍 Анализирую…")
        safety = [
            types.SafetySetting(category=c, threshold="BLOCK_NONE")
            for c in _SAFETY_CATS
        ]
        state = {"fallback": False}

        async def attempt():
            use_model = config.GEMINI_MODEL
            if state["fallback"]:
                use_model = (
                    getattr(config, "GEMINI_FALLBACK_MODEL", config.GEMINI_MODEL)
                    if hasattr(config, "GEMINI_FALLBACK_MODEL")
                    else "gemini-2.5-pro"
                )
            try:
                response = await client.aio.models.generate_content(
                    model=use_model,
                    contents=[uploaded, prompt],
                    config=types.GenerateContentConfig(
                        safety_settings=safety, max_output_tokens=8192
                    ),
                )
                return _text(response)
            except Exception as e:
                code = classify(e)
                if code == "GEMINI_429":
                    pool.report_quota_exceeded(key)  # ключ project-bound для URI → стоп
                if code == "GEMINI_503":
                    state["fallback"] = True
                raise

        try:
            return await retry_with_backoff(
                attempt, on_progress=on_progress, deadline_ts=deadline_ts
            )
        except Exception as e:
            logger.error("[GeminiVideo] generate code=%s detail=%s", classify(e), e)
            return message_for(e)
    finally:
        try:
            await client.aio.files.delete(name=uploaded.name)
        except Exception:
            pass
