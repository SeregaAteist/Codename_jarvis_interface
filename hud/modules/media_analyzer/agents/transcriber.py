"""Whisper.cpp transcription via subprocess."""

import asyncio
import logging
import re
from pathlib import Path

import config

logger = logging.getLogger(__name__)


async def extract_audio(video_path: Path) -> Path:
    """Extract 16 kHz mono WAV from video/voice file using ffmpeg."""
    wav_path = video_path.with_suffix(".wav")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(video_path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(wav_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg завершился с ошибкой: {stderr.decode()[:300]}")
    return wav_path


async def transcribe(audio_path: Path) -> str:
    """Run whisper.cpp binary and return clean transcript text."""
    cmd = [
        config.WHISPER_BIN,
        "-m", config.WHISPER_MODEL,
        "-f", str(audio_path),
        "-l", "auto",
        "-nt",  # no timestamps in output
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"whisper.cpp ошибка: {stderr.decode()[:300]}")

    text = stdout.decode("utf-8", errors="replace")
    # Strip any timestamp patterns that slipped through
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]\s*", "", text)
    return text.strip()
