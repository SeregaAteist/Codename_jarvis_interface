"""Универсальный обработчик голосовых сообщений через Gemini."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_PROMPT = "Транскрибируй это аудио точно. Только текст, без пояснений."


async def transcribe_voice(file_id: str, bot_token: str) -> str | None:
    """Скачивает голосовое из Telegram и транскрибирует через Gemini.

    Возвращает текст или None при ошибке.
    """
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"https://api.telegram.org/bot{bot_token}/getFile",
            params={"file_id": file_id},
        )
        r.raise_for_status()
        file_path = r.json()["result"]["file_path"]
        audio = await c.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}")
        audio.raise_for_status()

    try:
        from google import genai
        from google.genai import types

        from shared.llm.router import gemini_pool

        key = gemini_pool.get()
        if not key:
            logger.error("[voice] нет доступных ключей Gemini")
            return None

        client = genai.Client(api_key=key)
        part = types.Part.from_bytes(data=audio.content, mime_type="audio/ogg")
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[_PROMPT, part],
        )
        return response.text.strip()
    except Exception as e:
        logger.error("[voice] ошибка транскрипции: %s", e)
        return None
