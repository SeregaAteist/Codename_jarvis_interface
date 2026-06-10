"""Proactive suggestions — Jarvis acts before being asked."""
from datetime import datetime

from system.memory import load_memory, get_greeting_context


def get_proactive_suggestion() -> str | None:
    """Return action key if Jarvis should act proactively, else None."""
    hour = datetime.now().hour
    mem  = load_memory()
    today = datetime.now().strftime("%Y-%m-%d")

    # Morning briefing if no interactions yet today
    if 6 <= hour <= 9:
        interactions_today = [
            i for i in mem["interactions"]
            if i["time"].startswith(today)
        ]
        if not interactions_today:
            return "morning_brief"

    # Evening summary at 20:00
    if hour == 20:
        evening_done = any(
            i for i in mem["interactions"]
            if i["time"].startswith(today) and "вечер" in i.get("jarvis", "").lower()
        )
        if not evening_done:
            return "evening_summary"

    return None


def get_time_aware_greeting() -> str:
    """Compose a time-aware greeting with session context."""
    hour    = datetime.now().hour
    context = get_greeting_context()

    if hour < 6:
        tod = "Поздняя ночь, сэр."
    elif hour < 12:
        tod = "Доброе утро, сэр."
    elif hour < 17:
        tod = "Добрый день, сэр."
    elif hour < 22:
        tod = "Добрый вечер, сэр."
    else:
        tod = "Поздний вечер, сэр."

    return f"{tod} {context}. Все системы в норме."
