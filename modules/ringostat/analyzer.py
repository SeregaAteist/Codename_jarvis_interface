"""Analyzer — транскрипция и анализ звонков через Gemini."""
from __future__ import annotations
import logging, sys, os
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/Projects/jarvis"))
logger = logging.getLogger(__name__)

async def transcribe(audio_path: Path, call_meta: dict) -> str | None:
    """Транскрипция через Gemini. Активировать после решения фильтрации."""
    logger.info("[analyzer] TODO transcribe %s", audio_path)
    return None

async def analyze_history(lead_id: int, transcripts: list[str]) -> str:
    """Анализ истории звонков → досье по сделке."""
    if not transcripts:
        return ""
    from shared.llm import router
    prompt = f"""Проанализируй историю звонков по сделке #{lead_id} и составь досье:

Транскрипты:
{chr(10).join(f'--- Звонок {i+1} ---{chr(10)}{t}' for i,t in enumerate(transcripts))}

Формат:
**Клиент:** кто, что хочет, бюджет
**Договорённости:** список конкретных обещаний
**Возражения:** что беспокоит клиента
**Следующий шаг:** что нужно сделать
**Риски:** что может сорвать сделку
"""
    return await router.generate("quick_analysis", prompt)
