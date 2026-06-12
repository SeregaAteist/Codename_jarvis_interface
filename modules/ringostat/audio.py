"""Audio — скачивание записей звонков."""
from __future__ import annotations
import logging, os
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)
TMP = Path(os.getenv("JARVIS_ROOT", os.path.expanduser("~/Projects/jarvis"))) / "tmp" / "calls"

async def download(call_id: str, audio_url: str) -> Path | None:
    """Скачать аудио звонка. Активировать после решения фильтрации."""
    if not audio_url:
        return None
    TMP.mkdir(parents=True, exist_ok=True)
    dest = TMP / f"{call_id}.mp3"
    if dest.exists():
        return dest
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(audio_url)
            dest.write_bytes(r.content)
        logger.info("[audio] скачан звонок %s → %s", call_id, dest)
        return dest
    except Exception as e:
        logger.error("[audio] ошибка %s: %s", call_id, e)
        return None

def cleanup(call_id: str) -> None:
    (TMP / f"{call_id}.mp3").unlink(missing_ok=True)
