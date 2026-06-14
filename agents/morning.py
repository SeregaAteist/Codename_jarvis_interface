"""MorningBriefingAgent — утренний брифинг для владельца."""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime

from agents.base import BaseAgent
from agents.registry import register

logger = logging.getLogger(__name__)


@register
class MorningBriefingAgent(BaseAgent):
    name = "morning_briefing"
    icon = "☀"

    async def execute(self, task: str = "", **kwargs) -> str:  # type: ignore[override]
        sections = []
        sections.append(await self._services_status())
        sections.append(await self._rafail_summary())
        sections.append(await self._calls_summary())
        sections.append(await self._anime_summary())

        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        report = f"☀️ Доброе утро! {now}\n\n" + "\n\n".join(s for s in sections if s)

        try:
            from modules.bots.notify_bot import send_urgent

            await send_urgent(report)
        except Exception as e:
            logger.error("send_urgent failed: %s", e)

        return report

    async def _services_status(self) -> str:
        try:
            result = subprocess.run(
                ["launchctl", "list"], capture_output=True, text=True, timeout=5
            )
            jarvis_lines = [ln for ln in result.stdout.splitlines() if "jarvis" in ln]
            ok = sum(1 for ln in jarvis_lines if "\t0\t" in ln)
            fail = sum(1 for ln in jarvis_lines if ("\t-15\t" in ln or "\t-9\t" in ln))
            total = len(jarvis_lines)
            status = "✅ всі працюють" if fail == 0 else f"⚠️ {fail} впали"
            return f"🔧 Сервіси: {status} ({ok}/{total})"
        except Exception as e:
            return f"🔧 Сервіси: помилка перевірки — {e}"

    async def _rafail_summary(self) -> str:
        try:
            import sys

            sys.path.insert(0, os.path.expanduser("~/Projects/jarvis"))
            from modules.rafail.db import connect

            with connect() as c:
                pending = c.execute(
                    "SELECT COUNT(*) FROM processed WHERE status='pending'"
                ).fetchone()[0]
                approved = c.execute(
                    "SELECT COUNT(*) FROM processed WHERE status='approved'"
                    " AND date(created_at)=date('now')"
                ).fetchone()[0]
                materials = c.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
            return (
                f"📚 Рафаіл: {pending} чекають одобрення, "
                f"{approved} одобрено сьогодні, {materials} матеріалів"
            )
        except Exception as e:
            return f"📚 Рафаіл: помилка — {e}"

    async def _calls_summary(self) -> str:
        try:
            from pathlib import Path

            calls_dir = Path(os.path.expanduser("~/Projects/jarvis/data/calls"))
            if not calls_dir.exists():
                return ""
            count = len(list(calls_dir.glob("*.mp3")))
            return f"📞 Дзвінки: {count} записів"
        except Exception:
            return ""

    async def _anime_summary(self) -> str:
        try:
            sys_path = os.path.expanduser("~/Projects/jarvis/modules/anime-monitor")
            import sys

            if sys_path not in sys.path:
                sys.path.insert(0, sys_path)
            from agents.db_agent import get_all_snapshot  # type: ignore[import]

            snapshot = get_all_snapshot()
            return f"🎌 Аніме каталог: {len(snapshot)} тайтлів"
        except Exception:
            return ""


# ── Обратная совместимость (старый MorningAgent) ──────────────────────────────


@register
class MorningAgent:
    """Legacy wrapper — kept for any existing callers."""

    name = "morning"
    icon = "☀"

    def __init__(self, lat: float, lon: float, city: str, rss_feeds: list[str]) -> None:
        self.lat = lat
        self.lon = lon
        self.city = city
        self.feeds = rss_feeds

    def ask(self, _prompt: str = "") -> str:

        now = datetime.now()
        parts = [self._greeting(now), self._weather(), self._news()]
        return "\n".join(p for p in parts if p)

    def _greeting(self, now: datetime) -> str:
        h = now.hour
        if h < 6:
            tod = "Доброй ночи"
        elif h < 12:
            tod = "Доброе утро"
        elif h < 18:
            tod = "Добрый день"
        else:
            tod = "Добрый вечер"
        return f"{tod}! Сегодня {now.strftime('%A, %d %B %Y')}."

    def _weather(self) -> str:
        import json
        import urllib.request

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.lat}&longitude={self.lon}"
            "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            "&timezone=Europe%2FKiev&forecast_days=1"
        )
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                d = json.loads(r.read())
            c, dd = d["current"], d["daily"]
            code = c.get("weather_code", 0)
            desc = _WMO.get(code, "переменная облачность")
            temp = round(c["temperature_2m"])
            wind = round(c["wind_speed_10m"])
            hum = round(c["relative_humidity_2m"])
            hi, lo = round(dd["temperature_2m_max"][0]), round(
                dd["temperature_2m_min"][0]
            )
            rain = round(dd["precipitation_sum"][0], 1)
            rain_s = f", осадки {rain} мм" if rain > 0 else ""
            return (
                f"Погода в {self.city}: {desc}, {temp}°C "
                f"(днём {hi}°, ночью {lo}°). "
                f"Ветер {wind} км/ч, влажность {hum}%{rain_s}."
            )
        except Exception as e:
            return f"Погода недоступна: {e}"

    def _news(self) -> str:
        headlines = []
        for url in self.feeds[:3]:
            try:
                import feedparser  # type: ignore[import]

                feed = feedparser.parse(url)
                for entry in feed.entries[:2]:
                    t = entry.get("title", "").strip()
                    if t:
                        headlines.append(t)
            except Exception:
                continue
        if not headlines:
            return ""
        items = "\n".join(f"  • {h}" for h in headlines[:5])
        return f"Главные новости:\n{items}"


_WMO = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "туман с инеем",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    61: "лёгкий дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "лёгкий снег",
    73: "снег",
    75: "сильный снег",
    80: "ливневый дождь",
    81: "ливень",
    82: "сильный ливень",
    85: "снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}
