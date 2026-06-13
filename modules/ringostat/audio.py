"""Audio — скачивание записей звонков Ringostat."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from shared.config.settings import get_settings

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(os.path.expanduser("~/Projects/jarvis/data/calls"))


class AudioDownloader:
    """Скачивает аудио записи звонков."""

    def __init__(self) -> None:
        self._dir = AUDIO_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    async def download(self, call_id: str, audio_url: str) -> Path | None:
        """Скачать аудио звонка по ссылке из webhook."""
        if not audio_url:
            logger.warning("[audio] нет URL для звонка %s", call_id)
            return None

        dest = self._dir / f"{call_id}.mp3"
        if dest.exists():
            logger.info("[audio] уже скачан: %s", call_id)
            return dest

        try:
            s = get_settings()
            headers: dict[str, str] = {}
            if s.ringostat_auth_key:
                headers["Authorization"] = f"Bearer {s.ringostat_auth_key}"

            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
                r = await c.get(audio_url, headers=headers)
                r.raise_for_status()
                dest.write_bytes(r.content)

            logger.info(
                "[audio] скачан: %s → %s (%.1f KB)",
                call_id,
                dest,
                dest.stat().st_size / 1024,
            )
            return dest

        except Exception as e:
            logger.error("[audio] ошибка скачивания %s: %s", call_id, e)
            return None

    def cleanup(self, call_id: str) -> None:
        """Удалить аудио после обработки."""
        (self._dir / f"{call_id}.mp3").unlink(missing_ok=True)

    def get_cached(self, call_id: str) -> Path | None:
        path = self._dir / f"{call_id}.mp3"
        return path if path.exists() else None


_downloader: AudioDownloader | None = None


def get_downloader() -> AudioDownloader:
    global _downloader
    if _downloader is None:
        _downloader = AudioDownloader()
    return _downloader


# backward compat
async def download(call_id: str, audio_url: str) -> Path | None:
    return await get_downloader().download(call_id, audio_url)


def cleanup(call_id: str) -> None:
    get_downloader().cleanup(call_id)
