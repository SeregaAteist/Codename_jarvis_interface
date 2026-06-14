"""Ollama local LLM agent — offline second brain for Jarvis."""

import json
import subprocess
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"

try:
    from core.personality import JARVIS_SYSTEM_PROMPT as _JARVIS_SYSTEM
except ImportError:
    _JARVIS_SYSTEM = (
        "Ты Джарвис — персональный AI ассистент Сергея. "
        "Отвечай только по-русски. Кратко и по делу. "
        "Всегда обращайся 'сэр'. Стиль как у Пола Беттани в Iron Man."
    )


def ensure_running() -> bool:
    """Start ollama serve if not already running. Returns True when ready."""
    if is_available():
        return True
    print("[ollama] not running — starting...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(15):  # wait up to 15s
            time.sleep(1)
            if is_available():
                print("[ollama] started")
                return True
    except FileNotFoundError:
        print("[ollama] binary not found")
    print("[ollama] failed to start")
    return False


def is_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def ask(prompt: str, model: str = "mistral", system: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7, "num_ctx": 4096},
        }
    ).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        return data["message"]["content"]
    except urllib.error.URLError:
        return "Ollama недоступен."
    except Exception as e:
        return f"Ollama ошибка: {e}"


def ask_jarvis(prompt: str, model: str = "mistral") -> str:
    try:
        from core.personality import build_system_prompt

        system = build_system_prompt()
    except Exception:
        system = _JARVIS_SYSTEM

    response = ask(prompt, model=model, system=system)
    return response


class OllamaAgent:
    name = "ollama"
    icon = "⬡"

    def __init__(self, model: str = "mistral"):
        self.model = model

    def is_available(self) -> bool:
        return is_available()

    def ask(self, prompt: str) -> str:
        return ask_jarvis(prompt, model=self.model)


if __name__ == "__main__":
    print("Ollama доступен:", is_available())
    print("Модели:", list_models())
    if is_available():
        print(ask_jarvis("Представься и скажи что умеешь"))
