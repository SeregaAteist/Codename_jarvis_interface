"""URL downloader — yt-dlp wrapper for TikTok, YouTube, Instagram, etc."""

from __future__ import annotations

import asyncio
import logging
import uuid

import config

logger = logging.getLogger(__name__)

YTDLP_BIN = "/opt/homebrew/bin/yt-dlp"

SUPPORTED_DOMAINS = [
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "vimeo.com",
    "facebook.com",
    "fb.watch",
    "twitch.tv",
    "pinterest.com",
]


def is_supported_url(text: str) -> bool:
    return any(domain in text.lower() for domain in SUPPORTED_DOMAINS)


async def download_url(url: str) -> dict:
    """
    Download video from URL via yt-dlp.
    Returns: {video_path, subtitles, title, description}
    """
    out_id = uuid.uuid4().hex
    out_path = config.TMP_DIR / f"{out_id}.mp4"
    subs_path = config.TMP_DIR / f"{out_id}.subs.txt"

    # Download video + subtitles
    cmd = [
        YTDLP_BIN,
        "--no-playlist",
        "--max-filesize",
        "50m",
        "--write-auto-sub",
        "--sub-lang",
        "ru,en",
        "--convert-subs",
        "srt",
        "--write-description",
        "-o",
        str(config.TMP_DIR / f"{out_id}.%(ext)s"),
        "--merge-output-format",
        "mp4",
        "--quiet",
        url,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

    if not out_path.exists():
        # Try to find any downloaded file
        matches = list(config.TMP_DIR.glob(f"{out_id}.*"))
        video_files = [
            f for f in matches if f.suffix in (".mp4", ".webm", ".mkv", ".mov")
        ]
        if video_files:
            out_path = video_files[0]
        else:
            err = stderr.decode()[:200] if stderr else "файл не скачан"
            raise RuntimeError(f"yt-dlp не скачал видео: {err}")

    # Extract subtitles/description as transcript
    transcript = ""
    for ext in (".ru.srt", ".en.srt", ".ru.vtt", ".en.vtt"):
        sub_file = config.TMP_DIR / f"{out_id}{ext}"
        if sub_file.exists():
            raw = sub_file.read_text(errors="ignore")
            # Strip SRT timestamps
            lines = [
                l.strip()
                for l in raw.splitlines()
                if l.strip() and not l.strip().isdigit() and "-->" not in l
            ]
            transcript = " ".join(lines)[:3000]
            sub_file.unlink(missing_ok=True)
            break

    desc_file = config.TMP_DIR / f"{out_id}.description"
    description = ""
    if desc_file.exists():
        description = desc_file.read_text(errors="ignore")[:500]
        desc_file.unlink(missing_ok=True)

    # Get title via yt-dlp --get-title
    title = url
    try:
        title_proc = await asyncio.create_subprocess_exec(
            YTDLP_BIN,
            "--get-title",
            "--no-playlist",
            "--quiet",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(title_proc.communicate(), timeout=15)
        if stdout:
            title = stdout.decode().strip()[:100]
    except Exception:
        pass

    return {
        "video_path": out_path,
        "transcript": transcript,
        "title": title,
        "description": description,
    }
