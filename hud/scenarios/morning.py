"""Morning briefing: greeting + time + Open-Meteo weather only."""

import json
import urllib.request
from datetime import datetime


def get_weather(lat: float, lon: float) -> dict:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&timezone=Europe%2FKiev&forecast_days=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = json.loads(r.read())
        c = data["current"]
        d = data["daily"]
        return {
            "temp": round(c["temperature_2m"]),
            "wind": round(c["wind_speed_10m"]),
            "desc": _wmo(c["weather_code"]),
            "max": round(d["temperature_2m_max"][0]),
            "min": round(d["temperature_2m_min"][0]),
            "precip": round(d["precipitation_sum"][0], 1),
            "ok": True,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def build_morning_prompt(config: dict):
    name = config["user"]["name"]
    city = config["user"]["city"]
    lat = config["weather"]["lat"]
    lon = config["weather"]["lon"]

    now = datetime.now()
    h = now.hour
    if h < 6:
        tod = "Доброй ночи"
    elif h < 12:
        tod = "Доброе утро"
    elif h < 18:
        tod = "Добрый день"
    else:
        tod = "Добрый вечер"

    weather = get_weather(lat, lon)

    if weather["ok"]:
        w = weather
        weather_text = (
            f"Погода в {city}: {w['desc']}, {w['temp']}°C "
            f"(макс {w['max']}°, мин {w['min']}°), ветер {w['wind']} км/ч"
        )
        if w["precip"] > 0:
            weather_text += f", осадки {w['precip']} мм"
    else:
        weather_text = "Данные о погоде временно недоступны."

    prompt = (
        f"Ты — персональный ИИ-ассистент Jarvis. "
        f"Сейчас {now.strftime('%H:%M')}, {now.strftime('%d %B %Y')}. "
        f"{tod}, {name}!\n\n"
        f"{weather_text}\n\n"
        f"Составь короткое приветствие для {name}: поздоровайся, "
        f"скажи о погоде одним-двумя предложениями с советом по одежде, "
        f"пожелай хорошего дня. "
        f"Только текст для озвучки, без разметки, без новостей."
    )

    return prompt, {"weather": weather, "news": []}


def _wmo(code: int) -> str:
    m = {
        0: "ясно",
        1: "преимущественно ясно",
        2: "переменная облачность",
        3: "пасмурно",
        45: "туман",
        48: "изморозь",
        51: "лёгкая морось",
        53: "морось",
        55: "густая морось",
        61: "небольшой дождь",
        63: "дождь",
        65: "сильный дождь",
        71: "небольшой снег",
        73: "снег",
        75: "сильный снег",
        80: "ливень",
        81: "ливни",
        82: "сильный ливень",
        95: "гроза",
        96: "гроза с градом",
        99: "гроза с сильным градом",
    }
    return m.get(code, "переменная облачность")
