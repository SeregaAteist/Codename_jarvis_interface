"""Morning briefing: weather (Open-Meteo) + RSS headlines."""
import json
import urllib.request
from datetime import datetime


class MorningAgent:
    name = "morning"
    icon = "☀"

    def __init__(self, lat: float, lon: float, city: str, rss_feeds: list[str]):
        self.lat   = lat
        self.lon   = lon
        self.city  = city
        self.feeds = rss_feeds

    def ask(self, _prompt: str = "") -> str:
        now   = datetime.now()
        parts = [self._greeting(now), self._weather(), self._news()]
        return "\n".join(p for p in parts if p)

    # ── private ──────────────────────────────────────────────────────────────

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
            code  = c.get("weather_code", 0)
            desc  = _WMO.get(code, "переменная облачность")
            temp  = round(c["temperature_2m"])
            wind  = round(c["wind_speed_10m"])
            hum   = round(c["relative_humidity_2m"])
            hi, lo = round(dd["temperature_2m_max"][0]), round(dd["temperature_2m_min"][0])
            rain  = round(dd["precipitation_sum"][0], 1)
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
                import feedparser
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
    0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность",
    3: "пасмурно", 45: "туман", 48: "туман с инеем",
    51: "лёгкая морось", 53: "морось", 55: "сильная морось",
    61: "лёгкий дождь", 63: "дождь", 65: "сильный дождь",
    71: "лёгкий снег", 73: "снег", 75: "сильный снег",
    80: "ливневый дождь", 81: "ливень", 82: "сильный ливень",
    85: "снегопад", 86: "сильный снегопад",
    95: "гроза", 96: "гроза с градом", 99: "сильная гроза с градом",
}
