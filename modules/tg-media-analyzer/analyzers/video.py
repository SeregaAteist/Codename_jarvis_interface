"""Video analyzer — extracts audio + transcribes + analyzes frames."""
from __future__ import annotations
import asyncio
import logging
import uuid
from pathlib import Path

import config

logger = logging.getLogger(__name__)


async def extract_audio(video_path: Path) -> Path:
    audio_path = config.TMP_DIR / f"{uuid.uuid4().hex}.wav"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", str(video_path),
        "-ar", "16000", "-ac", "1", "-f", "wav",
        str(audio_path), "-y",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    return audio_path


async def transcribe(audio_path: Path) -> str:
    whisper_bin = config.WHISPER_BIN if hasattr(config, "WHISPER_BIN") else ""
    if not whisper_bin or not Path(whisper_bin).exists():
        return "[транскрипция недоступна — whisper не найден]"
    try:
        proc = await asyncio.create_subprocess_exec(
            whisper_bin, "-m", config.WHISPER_MODEL,
            "-f", str(audio_path), "--language", "ru",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()
    except Exception as e:
        logger.error("[Transcribe] %s", e)
        return f"[ошибка транскрипции: {e}]"
