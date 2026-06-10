"""Reasoning Core — central orchestrator for Jarvis."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Response:
    text:  str
    agent: str
    intent: str = "general"
    ok:    bool = True


# ── Intent patterns ───────────────────────────────────────────────────────────

_INTENTS: list[tuple[str, re.Pattern]] = [
    ("morning",  re.compile(r"\b(доброе утро|добрый день|добрый вечер|как дела|как настроение|утренний|что нового|привет)\b", re.I)),
    ("mac",      re.compile(r"\b(открой|открыть|запусти|запустить|закрой|громкость|заблокируй|блокировка|уведомление|яркость|скриншот|выполни команду)\b", re.I)),
    ("ollama",   re.compile(r"\b(быстро|локально|офлайн|без интернета|локальная модель)\b", re.I)),
    # monitor before weather so "температура процессора" goes to monitor not weather
    ("monitor",  re.compile(
        r"(?:состояние системы|как система|системный отчёт|отчёт системы"
        r"|температур"
        r"|батаре|заряд"
        r"|памят|\bram\b"
        r"|диск|свободно на диске"
        r"|что грузит|топ процесс|кто грузит"
        r"|загрузк|\bcpu\b|процессор"
        r")", re.I
    )),
    ("weather",  re.compile(r"\b(погода|дождь|ветер|прогноз|осадки|облачно)\b", re.I)),
    ("news",     re.compile(r"\b(новости|что происходит|расскажи новости|последние события|заголовки)\b", re.I)),
    ("memory",   re.compile(r"\b(запомни|запиши|заметку|заметка|что ты знаешь|что знаешь обо мне|мои заметки|что записал|статистика|сколько мы|сколько раз)\b", re.I)),
    ("search",   re.compile(r"\b(найди|поищи|что такое|кто такой|погугли|поищи|найти|нагугли)\b", re.I)),
    ("price",    re.compile(r"\b(цена|сколько стоит|стоимость|почём|купить|цены на)\b", re.I)),
    ("open_url", re.compile(r"\b(открой сайт|перейди на|открой https?://|открой www\.)\b", re.I)),
    ("fetch",    re.compile(r"\b(прочитай страницу|что на сайте|прочти сайт)\b", re.I)),
]


class ReasoningCore:
    """
    Receives any request (voice or text), classifies intent, routes to the
    appropriate agent, and returns a structured Response.
    """

    def __init__(self, router, on_status: Callable[[str, str], None] | None = None):
        """
        router  – system.router.Router instance
        on_status – callback(state, agent) for broadcasting status changes
        """
        self.router    = router
        self._status   = on_status or (lambda s, a: None)
        self._history: list[dict] = []  # last N turns for context

    # ── Public API ────────────────────────────────────────────────────────────

    def process(self, text: str) -> Response:
        """Classify → route → return Response."""
        text = text.strip()
        if not text:
            return Response("Пожалуйста, повтори запрос.", "system")

        # Special OS-level commands handled here
        special = _check_special(text)
        if special:
            return Response(special, "system", "system")

        intent = self._classify(text)
        self._status("thinking", intent)

        try:
            reply, agent = self.router.route_intent(text, intent, self._history[-6:])
        except Exception as e:
            reply  = f"Ошибка агента: {e}"
            agent  = "error"

        # Store turn in history (keep last 10 pairs)
        self._history.append({"role": "user",      "content": text})
        self._history.append({"role": "assistant",  "content": reply, "agent": agent})
        if len(self._history) > 20:
            self._history = self._history[-20:]

        return Response(reply, agent, intent)

    # ── Private ───────────────────────────────────────────────────────────────

    def _classify(self, text: str) -> str:
        """Fast regex-based intent classification."""
        t = text.lower()
        for intent, pat in _INTENTS:
            if pat.search(t):
                return intent
        return "general"


# ── System-level special commands (AirPlay, etc.) ─────────────────────────────

_AIRPLAY_SCRIPT = """
tell application "System Events"
    tell process "SystemUIServer"
        repeat with i in (every menu bar item of menu bar 1)
            if description of i contains "AirPlay" or description of i contains "Display" then
                click i
                return
            end if
        end repeat
    end tell
end tell
"""


def _check_special(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bна телевизор\b|\bна экран\b|\bairplay\b", t):
        subprocess.Popen(["osascript", "-e", _AIRPLAY_SCRIPT])
        return "Запускаю AirPlay зеркалирование экрана."
    return None
