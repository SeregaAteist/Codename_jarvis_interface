"""Формирование итогового Telegram-сообщения брифинга."""
from __future__ import annotations

from datetime import datetime


def format_briefing(summary: str, post_count: int) -> str:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    return (
        "🌅 Доброе утро, сэр. Утренний брифинг.\n\n"
        f"🤖 AI-новости ({post_count} постов из Reddit):\n{summary}\n\n"
        "📡 Источники: r/artificial · r/MachineLearning · r/LocalLLaMA\n"
        f"⏰ {now}"
    )
