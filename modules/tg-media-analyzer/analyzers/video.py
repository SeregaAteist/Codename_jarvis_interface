"""Video analyzer — extracts frames for vision analysis, transcribes if whisper available."""
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
    return audio_path if audio_path.exists() else video_path


async def extract_frames(video_path: Path, n: int = 4) -> list[Path]:
    """Extract N evenly spaced frames from video as JPEG."""
    frames = []
    for i in range(n):
        out = config.TMP_DIR / f"{uuid.uuid4().hex}_frame{i}.jpg"
        # seek to i/(n-1) relative position
        pct = i / max(n - 1, 1)
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", str(video_path),
            "-vf", f"select=eq(pict_type\\,I)",
            "-vframes", "1",
            "-ss", str(pct),
            str(out), "-y",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        if out.exists() and out.stat().st_size > 0:
            frames.append(out)
    return frames


async def transcribe(audio_path: Path) -> str:
    whisper_bin = getattr(config, "WHISPER_BIN", "")
    whisper_model = getattr(config, "WHISPER_MODEL", "")
    if not whisper_bin or not Path(whisper_bin).exists():
        return ""  # пустая строка — не ошибка, просто нет whisper
    try:
        proc = await asyncio.create_subprocess_exec(
            whisper_bin, "-m", whisper_model,
            "-f", str(audio_path), "--language", "ru",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()
    except Exception as e:
        logger.error("[Transcribe] %s", e)
        return ""
