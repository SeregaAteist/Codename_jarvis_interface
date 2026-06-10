"""Weather from Open-Meteo (no API key)."""
import json
import urllib.request

try:
    from system.cache import weather_cache as _weather_cache
except ImportError:
    _weather_cache = None

_WMO = {
    0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность",
    3: "пасмурно", 45: "туман", 51: "морось", 53: "морось",
    61: "лёгкий дождь", 63: "дождь", 65: "сильный дождь",
    71: "лёгкий снег", 73: "снег", 75: "сильный снег",
    80: "ливень", 95: "гроза", 99: "гроза с градом",
}


class WeatherAgent:
    name = "weather"
    icon = "☁"

    def __init__(self, lat: float = 46.4825, lon: float = 30.7233, city: str = "Одесса"):
        self.lat, self.lon, self.city = lat, lon, city

    def ask(self, _prompt: str = "") -> str:
        cache_key = f"weather_{self.lat}_{self.lon}"
        if _weather_cache:
            cached = _weather_cache.get(cache_key)
            if cached:
                return cached

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.lat}&longitude={self.lon}"
            "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=Europe%2FKiev&forecast_days=1"
        )
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                d = json.loads(r.read())
            c, dd = d["current"], d["daily"]
            desc   = _WMO.get(c.get("weather_code", 0), "переменная облачность")
            temp   = round(c["temperature_2m"])
            wind   = round(c["wind_speed_10m"])
            hum    = round(c["relative_humidity_2m"])
            hi     = round(dd["temperature_2m_max"][0])
            lo     = round(dd["temperature_2m_min"][0])
            result = (
                f"Погода в {self.city}: {desc}, {temp}°C "
                f"(днём {hi}°, ночью {lo}°). "
                f"Ветер {wind} км/ч, влажность {hum}%."
            )
            if _weather_cache:
                _weather_cache.set(cache_key, result)
            return result
        except Exception as e:
            return f"Погода недоступна: {e}"
