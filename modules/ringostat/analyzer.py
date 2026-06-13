"""CallAnalyzer — транскрипция и анализ звонков через Gemini."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from shared.llm.router import get_router

logger = logging.getLogger(__name__)


@dataclass
class CallTranscript:
    call_id: str
    duration: int
    phone: str
    manager_name: str = ""
    transcript: str = ""
    summary: str = ""
    disposition: str = ""  # successful / unsuccessful / unknown
    objections: list[str] = field(default_factory=list)
    agreements: list[str] = field(default_factory=list)
    next_step: str = ""
    script_effectiveness: str = ""  # high / medium / low
    improvement_suggestions: list[str] = field(default_factory=list)


class CallTranscriber:
    """Транскрибирует аудио звонков через Gemini (google-generativeai)."""

    async def transcribe(self, audio_path: Path, call_meta: dict) -> str:
        """Транскрибировать аудио файл."""
        try:
            import google.generativeai as genai

            router = get_router()
            key: str = router._gemini_pool.get_key()
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.5-flash")

            audio_file = genai.upload_file(str(audio_path), mime_type="audio/mp3")
            response = model.generate_content(
                [
                    "Транскрибуй цей телефонний дзвінок точно. "
                    "Розділяй репліки: МЕНЕДЖЕР: ... / КЛІЄНТ: ... "
                    "Мова оригіналу. Тільки текст розмови.",
                    audio_file,
                ]
            )
            try:
                audio_file.delete()
            except Exception:
                pass

            return response.text

        except Exception as e:
            logger.error("[transcriber] ошибка транскрипции %s: %s", audio_path, e)
            return ""


class CallAnalyzer:
    """Анализирует транскрипт звонка и извлекает инсайты."""

    def __init__(self) -> None:
        self._router = get_router()

    async def analyze(self, transcript: str, call_meta: dict) -> CallTranscript:
        """Полный анализ транскрипта звонка."""
        call_id = call_meta.get("call_id", "unknown")
        phone = call_meta.get("caller_id", "")
        duration = call_meta.get("duration", 0)
        manager_name = call_meta.get("manager_name", "")

        if not transcript:
            return CallTranscript(
                call_id=call_id,
                duration=duration,
                phone=phone,
                manager_name=manager_name,
            )

        prompt = f"""
Проаналізуй транскрипт телефонного дзвінка менеджера LK Energy Group (продаж СЕС).

Транскрипт:
{transcript[:8000]}

Метадані:
- Менеджер: {manager_name}
- Тривалість: {duration} сек
- Телефон клієнта: {phone}

Поверни JSON:
{{
  "summary": "одне речення — суть дзвінка",
  "disposition": "successful/unsuccessful/unknown",
  "objections": ["заперечення 1", "заперечення 2"],
  "agreements": ["домовленість 1", "домовленість 2"],
  "next_step": "наступний крок",
  "script_effectiveness": "high/medium/low",
  "improvement_suggestions": ["порада 1", "порада 2"]
}}

Тільки JSON."""

        raw = await self._router.generate("quick_analysis", prompt)

        try:
            text = (
                raw.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            data = json.loads(text)
            return CallTranscript(
                call_id=call_id,
                duration=duration,
                phone=phone,
                manager_name=manager_name,
                transcript=transcript,
                summary=data.get("summary", ""),
                disposition=data.get("disposition", "unknown"),
                objections=data.get("objections", []),
                agreements=data.get("agreements", []),
                next_step=data.get("next_step", ""),
                script_effectiveness=data.get("script_effectiveness", "medium"),
                improvement_suggestions=data.get("improvement_suggestions", []),
            )
        except Exception as e:
            logger.error("[analyzer] ошибка парсинга JSON: %s", e)
            return CallTranscript(
                call_id=call_id,
                duration=duration,
                phone=phone,
                transcript=transcript,
                summary=raw[:200],
            )

    async def analyze_history(self, lead_id: int, transcripts: list[str]) -> str:
        """Анализ истории звонков по сделке → досье."""
        if not transcripts:
            return ""

        combined = "\n\n---\n\n".join(
            f"Дзвінок {i + 1}:\n{t}" for i, t in enumerate(transcripts)
        )

        prompt = f"""Проаналізуй всі дзвінки по угоді #{lead_id} і склади досьє.

Дзвінки:
{combined[:15000]}

Формат:
**Клієнт:** хто, що хоче, бюджет
**Домовленості:** конкретні обіцянки (по датах якщо є)
**Заперечення:** що турбує клієнта
**Наступний крок:** що треба зробити
**Ризики:** що може зірвати угоду"""

        return await self._router.generate("quick_analysis", prompt)


_transcriber: CallTranscriber | None = None
_analyzer: CallAnalyzer | None = None


def get_transcriber() -> CallTranscriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = CallTranscriber()
    return _transcriber


def get_analyzer() -> CallAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = CallAnalyzer()
    return _analyzer


# backward compat
async def transcribe(audio_path: Path, call_meta: dict) -> str:
    return await get_transcriber().transcribe(audio_path, call_meta)


async def analyze_history(lead_id: int, transcripts: list[str]) -> str:
    return await get_analyzer().analyze_history(lead_id, transcripts)
