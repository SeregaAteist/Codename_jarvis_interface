"""Claude API: media analysis and implementation generation."""

import base64
import logging
from pathlib import Path

import anthropic

import config

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

_ANALYZE_PROMPT = (
    "Проанализируй этот медиаконтент для системы J.A.R.V.I.S. HUD OS. Определи:\n"
    "1. **UI элементы и паттерны** — что показано на скриншотах/видео\n"
    "2. **Ключевые идеи и концепции** — что демонстрирует контент\n"
    "3. **Технологии и стек** — что используется, что применимо в J.A.R.V.I.S.\n"
    "4. **Потенциал реализации** — высокий/средний/низкий + обоснование\n"
    "Отвечай на русском. Конкретно, actionable."
)

_IMPLEMENT_PROMPT = (
    "На основе анализа сгенерируй конкретные инструкции по реализации для "
    "J.A.R.V.I.S. HUD OS (MacBook Air M2, Python 3.11, Electron, React, "
    "ChromaDB, Groq/Claude API):\n\n{analysis}\n\n"
    "Пошаговый план: какие файлы создать/изменить, конкретный код, команды установки. "
    "Отвечай на русском."
)


def _encode_image(path: Path) -> tuple[str, str]:
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    }
    media_type = media_types.get(path.suffix.lower(), "image/jpeg")
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return data, media_type


async def analyze_media(transcripts: list[str], image_paths: list[Path]) -> str:
    if not transcripts and not image_paths:
        return "Медиаконтент не обнаружен."

    content: list[dict] = []

    for img in image_paths[:10]:
        if img.stat().st_size > 4 * 1024 * 1024:
            logger.warning("Пропускаю большое изображение: %s", img.name)
            continue
        b64, mtype = _encode_image(img)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mtype, "data": b64},
        })

    if transcripts:
        content.append({
            "type": "text",
            "text": "Транскрипции аудио/видео:\n" + "\n---\n".join(transcripts),
        })

    content.append({"type": "text", "text": _ANALYZE_PROMPT})

    response = await _client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


async def generate_implementation(analysis: str) -> str:
    response = await _client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": _IMPLEMENT_PROMPT.format(analysis=analysis),
        }],
    )
    return response.content[0].text
