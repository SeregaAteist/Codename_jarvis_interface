"""Deep analysis — Claude Vision, triggered on 'В работу'."""
from __future__ import annotations
import base64
import logging
from pathlib import Path

import config
from pool.api_pool import SimplePool

logger = logging.getLogger(__name__)

_claude_pool = SimplePool(config.CLAUDE_KEYS, "claude")

DEEP_PROMPT = """На основе этого медиаконтента создай детальный план внедрения для J.A.R.V.I.S.

Стек системы: MacBook Air M2, Python 3.11, Electron + React, FastAPI, ChromaDB, Groq/Gemini/Claude API.

**📋 ДЕТАЛЬНЫЙ АНАЛИЗ**
(что именно показано, технологии, паттерны)

**🏗️ АРХИТЕКТУРА ВНЕДРЕНИЯ**
(какой модуль/агент создать, как интегрировать)

**📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ/ИЗМЕНЕНИЯ**
(конкретные пути в ~/Projects/jarvis/)

**💻 КЛЮЧЕВОЙ КОД**
(минимальный рабочий пример)

**📦 ЗАВИСИМОСТИ**
(pip install / npm install команды)

**✅ ШАГИ ВНЕДРЕНИЯ**
(нумерованный план, от простого к сложному)

Отвечай на русском. Максимально конкретно и actionable."""


async def deep_analyze(
    quick_summary: str,
    image_paths: list[Path],
    transcripts: list[str],
) -> str:
    key = _claude_pool.get()
    if not key:
        return "⚠️ Claude недоступен — добавьте ANTHROPIC_API_KEY в .env"
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=key)
        content: list[dict] = []
        for img_path in image_paths[:8]:
            if not img_path.exists() or img_path.stat().st_size > config.MAX_IMAGE_SIZE:
                continue
            ext = img_path.suffix.lower().lstrip(".")
            mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
            data = base64.standard_b64encode(img_path.read_bytes()).decode()
            content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
        if transcripts:
            content.append({"type": "text", "text": "Транскрипции:\n" + "\n---\n".join(transcripts)})
        if quick_summary:
            content.append({"type": "text", "text": f"Предварительный анализ (Gemini):\n{quick_summary}"})
        content.append({"type": "text", "text": DEEP_PROMPT})
        response = await client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text
    except Exception as e:
        if any(x in str(e).lower() for x in ("quota", "529", "overloaded", "rate")):
            _claude_pool.report_quota_exceeded(key)
        logger.error("[DeepPipeline] %s", e)
        return f"⚠️ Ошибка Claude: {e}"
