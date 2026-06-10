"""Jarvis preferences and learned facts — persistent across sessions."""
import json
import os
from datetime import datetime

PREFS_FILE = os.path.expanduser("~/jarvis/data/preferences.json")

_DEFAULTS = {
    "voice_speed": 175,
    "response_length": "short",
    "preferred_agent": "ollama",
    "topics_of_interest": [],
    "disliked_topics": [],
    "custom_commands": {},
    "notes": [],
    "learned": {},
}


def load_prefs() -> dict:
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    p = _DEFAULTS.copy()
    save_prefs(p)
    return p


def save_prefs(data: dict):
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    tmp = PREFS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PREFS_FILE)


def add_note(note: str):
    p = load_prefs()
    p["notes"].append({"text": note, "time": datetime.now().isoformat()})
    p["notes"] = p["notes"][-50:]
    save_prefs(p)


def get_notes() -> list:
    return load_prefs().get("notes", [])


def learn(key: str, value: str):
    p = load_prefs()
    p["learned"][key] = {"value": value, "learned_at": datetime.now().isoformat()}
    save_prefs(p)


def recall(key: str) -> str | None:
    item = load_prefs()["learned"].get(key)
    return item["value"] if item else None


def get_all_learned() -> dict:
    return load_prefs().get("learned", {})


def add_custom_command(trigger: str, action: str):
    p = load_prefs()
    p["custom_commands"][trigger] = action
    save_prefs(p)


def get_custom_commands() -> dict:
    return load_prefs().get("custom_commands", {})
