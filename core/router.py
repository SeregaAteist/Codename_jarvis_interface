"""Routes classified intents to the appropriate agent."""
from __future__ import annotations
import re
import subprocess

# ── Browser intent patterns ───────────────────────────────────────────────────
_SEARCH_STRIP = re.compile(r"\b(найди|поищи|что такое|кто такой|погугли|нагугли|найти)\s*", re.I)
_PRICE_STRIP  = re.compile(r"\b(цена|сколько стоит|стоимость|почём|купить|цены на)\s*", re.I)
_URL_PAT      = re.compile(r"https?://\S+|www\.\S+|\S+\.\w{2,4}(?:/\S*)?")
_FETCH_STRIP  = re.compile(r"\b(прочитай страницу|что на сайте|прочти сайт)\s*", re.I)


# ── mac_control intent patterns ───────────────────────────────────────────────
_APP_PAT   = re.compile(r"\b(открой|запусти|открыть)\s+(.+)", re.I)
_VOL_PAT   = re.compile(r"\bгромкость\s+(\d+)", re.I)
_LOCK_PAT  = re.compile(r"\b(заблокируй|блокировка|заблокировать)\b", re.I)
_NOTIF_PAT = re.compile(r"\bуведомление\s+(.+)", re.I)


def _mac_dispatch(text: str) -> str | None:
    from agents.mac_control import open_app, set_volume, lock_screen, show_notification
    t = text.strip()
    m = _APP_PAT.search(t)
    if m:
        return open_app(m.group(2).strip().title())
    m = _VOL_PAT.search(t)
    if m:
        return set_volume(int(m.group(1)))
    if _LOCK_PAT.search(t):
        return lock_screen()
    m = _NOTIF_PAT.search(t)
    if m:
        return show_notification("JARVIS", m.group(1).strip())
    return None


def _claude_available() -> bool:
    """SDK key set AND claude.enabled=true in config."""
    import os, yaml
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        if not cfg.get("claude", {}).get("enabled", True):
            return False
    except Exception:
        pass
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return True
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False


class Router:
    """
    Holds all agents and routes intent → agent.
    Accepted intents: morning / mac / terminal / ollama / weather / news / general
    """

    def __init__(self, morning, terminal, wot, ollama, weather, rss, claude,
                 gemini=None, groq=None, xai=None, browser=None):
        self.morning  = morning
        self.terminal = terminal
        self.wot      = wot
        self.ollama   = ollama
        self.weather  = weather
        self.rss      = rss
        self.claude   = claude
        self.gemini   = gemini
        self.groq     = groq
        self.xai      = xai
        self.browser  = browser
        self._claude_ok: bool | None = None   # cached availability

    # ── Availability helpers ──────────────────────────────────────────────────

    def _check_claude(self) -> bool:
        """Cached check — re-evaluated every 60 s via reset."""
        if self._claude_ok is None:
            self._claude_ok = _claude_available()
        return self._claude_ok

    def get_best_agent(self) -> str:
        """Return name of the best available general-purpose agent."""
        if self.ollama.is_available():
            return "ollama"
        if self.groq and self.groq.is_available():
            return "groq"
        if self.xai and self.xai.is_available():
            return "xai"
        if self.gemini and self.gemini.is_available():
            return "gemini"
        if self._check_claude():
            return "claude"
        return "none"

    # ── Routing ───────────────────────────────────────────────────────────────

    def route_intent(
        self,
        text: str,
        intent: str,
        history: list[dict] | None = None,
    ) -> tuple[str, str]:
        """Returns (reply_text, agent_name)."""

        if intent == "morning":
            return self.morning.ask(), self.morning.name

        if intent in ("terminal", "mac"):
            result = _mac_dispatch(text)
            if result:
                return result, "mac"
            return self.terminal.ask(text), self.terminal.name

        if intent == "ollama":
            if self.ollama.is_available():
                return self.ollama.ask(text), self.ollama.name
            # Fall through to general

        if intent == "weather":
            return self.weather.ask(), self.weather.name

        if intent == "news":
            return self.rss.ask(), self.rss.name

        if intent == "memory":
            return _memory_dispatch(text), "system"

        if intent in ("search", "price", "open_url", "fetch"):
            return _browser_dispatch(text, intent, self.ollama), "browser"

        if intent == "monitor":
            return _monitor_dispatch(text), "system"

        # ── General / fallback: Ollama → Groq → xAI → Gemini → Claude → error
        prompt = _build_prompt(text, history)

        if self.ollama.is_available():
            return self.ollama.ask(prompt), self.ollama.name

        if self.groq and self.groq.is_available():
            return self.groq.ask(prompt), self.groq.name

        if self.xai and self.xai.is_available():
            return self.xai.ask(prompt), self.xai.name

        if self.gemini and self.gemini.is_available():
            return self.gemini.ask(prompt), self.gemini.name

        if self._check_claude():
            return self.claude.ask(prompt), self.claude.name

        return (
            "Нет доступного агента. Запустите Ollama или добавьте XAI_API_KEY / GROQ_API_KEY в .env.",
            "system",
        )

    # ── Legacy shim ───────────────────────────────────────────────────────────
    def route(self, text: str) -> tuple[str, str]:
        return self.route_intent(text, "general")


_LEARN_PAT = re.compile(r"запомни(?:\s+что)?\s+(.+)", re.I)
_NOTE_PAT  = re.compile(r"(?:заметку|запиши)\s*:?\s*(.+)", re.I)  # заметку (с у), not заметки


def _memory_dispatch(text: str) -> str:
    from core.preferences import learn, get_all_learned, add_note, get_notes
    from core.memory import get_stats_summary
    t = text.strip()

    # Check notes/stats BEFORE note-add pattern to avoid false matches
    if re.search(r"\bмои\s+заметки\b|что\s+записал", t, re.I):
        notes = get_notes()
        if not notes:
            return "Заметок пока нет, сэр."
        lines = [f"- {n['text']}" for n in notes[-5:]]
        return "Ваши последние заметки, сэр:\n" + "\n".join(lines)

    if re.search(r"знаешь\s+обо?\s+мне|знаешь\s+о\s+сергее", t, re.I):
        learned = get_all_learned()
        if not learned:
            return "Пока ничего не зафиксировано, сэр. Скажите «запомни» — и я запишу."
        lines = [f"- {k}: {v['value']}" for k, v in list(learned.items())[-10:]]
        return "Вот что я знаю о вас, сэр:\n" + "\n".join(lines)

    if re.search(r"статистик|сколько мы|сколько раз", t, re.I):
        s = get_stats_summary()
        top = ", ".join(f"«{k}»×{v}" for k, v in s["top_requests"]) or "нет данных"
        return (
            f"Статистика, сэр. Сессий: {s['session_count']}. "
            f"Взаимодействий: {s['total_interactions']}. "
            f"Пиковый час: {s['peak_hour']}. "
            f"Топ запросы: {top}."
        )

    # "запомни что я люблю кофе утром"
    m = _LEARN_PAT.search(t)
    if m:
        fact = m.group(1).strip()
        if ":" in fact:
            k, v = fact.split(":", 1)
        else:
            # Use first 3 words as key, full phrase as value
            words = fact.split()
            k = " ".join(words[:3])
            v = fact
        k, v = k.strip(), v.strip()
        learn(k, v)
        return f"Зафиксировано, сэр. {k}: {v}."

    # "сделай заметку: позвонить завтра"
    m = _NOTE_PAT.search(t)
    if m:
        note = m.group(1).strip()
        add_note(note)
        return f"Заметка добавлена, сэр: «{note}»."

    return "Уточните команду памяти, сэр: «запомни», «заметку», «мои заметки» или «статистика»."


def _monitor_dispatch(text: str) -> str:
    from core.monitor import monitor
    t = text.lower()

    if re.search(r"\b(топ процесс|что грузит|кто грузит)\b", t):
        return monitor.get_top_processes_report()
    if re.search(r"\b(температур)\b", t):
        return monitor.get_temp_report()
    if re.search(r"\b(батаре|заряд)\b", t):
        return monitor.get_battery_report()
    if re.search(r"\b(память|ram)\b", t):
        return monitor.get_ram_report()
    if re.search(r"\b(диск|свободно)\b", t):
        return monitor.get_disk_report()
    if re.search(r"\b(cpu|процессор|загрузка)\b", t):
        return monitor.get_cpu_report()
    # Default: full report
    return monitor.get_report()


def _browser_dispatch(text: str, intent: str, ollama) -> str:
    """Handle web search / price / fetch / open_url intents."""
    from agents.browser import smart_search, get_price, fetch_page, open_url_in_browser

    if intent == "open_url":
        urls = _URL_PAT.findall(text)
        if urls:
            return open_url_in_browser(urls[0])
        return "Не могу определить адрес сайта, сэр."

    if intent == "fetch":
        urls = _URL_PAT.findall(text)
        if not urls:
            return "Укажите адрес сайта, сэр."
        raw = fetch_page(urls[0])
        return _ollama_summarize(raw, f"Содержимое {urls[0]}", ollama)

    if intent == "price":
        product = _PRICE_STRIP.sub("", text).strip() or text
        raw     = get_price(product)
        return _ollama_summarize(raw, f"Цены на {product}", ollama, style="price")

    # intent == "search"
    query = _SEARCH_STRIP.sub("", text).strip() or text
    raw   = smart_search(query)
    return _ollama_summarize(raw, query, ollama)


def _ollama_summarize(raw: str, query: str, ollama, style: str = "search") -> str:
    """Ask Ollama to compress raw web content into a Jarvis-style reply."""
    if style == "price":
        prompt = (
            f"Найденные данные о ценах на «{query}»:\n{raw}\n\n"
            "Кратко сообщи найденные цены в 2-3 предложениях в стиле Джарвиса. Только факты."
        )
    else:
        prompt = (
            f"Результаты поиска по запросу «{query}»:\n{raw}\n\n"
            "Дай краткий ответ (2-3 предложения) в стиле Джарвиса. Только суть."
        )
    try:
        if ollama and ollama.is_available():
            return ollama.ask(prompt)
    except Exception:
        pass
    # Fallback: return raw snippets directly
    return raw[:500]


def _build_prompt(text: str, history: list[dict] | None) -> str:
    if not history:
        return text
    lines = [
        f"{'Пользователь' if h['role'] == 'user' else 'Джарвис'}: {h['content']}"
        for h in history[-6:]
    ]
    return "\n".join(lines) + f"\nПользователь: {text}"
