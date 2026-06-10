"""Jarvis persistent memory — interactions, patterns, preferences."""
import json
import os
import time
import threading
from datetime import datetime

MEMORY_FILE = os.path.expanduser("~/jarvis/data/memory.json")

# ── In-memory TTL cache (avoids disk read on every request) ──────────────────
_mem_cache: dict | None = None
_mem_cache_ts: float    = 0.0
_mem_cache_ttl: float   = 5.0   # seconds
_mem_lock = threading.Lock()


def _ensure_patterns(mem: dict) -> dict:
    """Migrate flat patterns dict to nested format."""
    p = mem.get("patterns", {})
    if not isinstance(p.get("hourly"), dict):
        mem["patterns"] = {"hourly": {}, "daily": {}, "common_requests": {}}
    return mem


def _default_memory() -> dict:
    return {
        "interactions": [],
        "patterns":     {"hourly": {}, "daily": {}, "common_requests": {}},
        "last_seen":    None,
        "session_count": 0,
        "total_interactions": 0,
    }


def load_memory() -> dict:
    global _mem_cache, _mem_cache_ts
    now = time.monotonic()
    with _mem_lock:
        if _mem_cache is not None and now - _mem_cache_ts < _mem_cache_ttl:
            return _mem_cache

    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    data = _default_memory()
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                data = _ensure_patterns(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    with _mem_lock:
        _mem_cache    = data
        _mem_cache_ts = now
    return data


def save_memory(data: dict):
    global _mem_cache, _mem_cache_ts
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    tmp = MEMORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MEMORY_FILE)
    os.chmod(MEMORY_FILE, 0o600)
    with _mem_lock:
        _mem_cache    = data
        _mem_cache_ts = time.monotonic()


def log_interaction(user_text: str, jarvis_response: str, agent: str = "ollama"):
    mem = load_memory()
    now = datetime.now()

    mem["interactions"].append({
        "time":   now.isoformat(),
        "user":   user_text,
        "jarvis": jarvis_response[:200],
        "agent":  agent,
    })

    hour = str(now.hour)
    day  = str(now.weekday())
    mem["patterns"]["hourly"][hour]  = mem["patterns"]["hourly"].get(hour, 0) + 1
    mem["patterns"]["daily"][day]    = mem["patterns"]["daily"].get(day, 0) + 1

    key = " ".join(user_text.lower().split()[:3])
    mem["patterns"]["common_requests"][key] = \
        mem["patterns"]["common_requests"].get(key, 0) + 1

    mem["last_seen"]          = now.isoformat()
    mem["session_count"]      = mem.get("session_count", 0) + 1
    mem["total_interactions"] = mem.get("total_interactions", 0) + 1
    mem["interactions"]       = mem["interactions"][-200:]
    save_memory(mem)


def get_context_summary(last_n: int = 5) -> str:
    mem = load_memory()
    if not mem["interactions"]:
        return ""
    lines = []
    for i in mem["interactions"][-last_n:]:
        t = i["time"][11:16]
        lines.append(f"[{t}] Сергей: {i['user'][:60]}")
        lines.append(f"[{t}] Джарвис: {i['jarvis'][:100]}")
    return "\n".join(lines)


def get_frequent_requests(top_n: int = 5) -> list:
    mem = load_memory()
    reqs = mem["patterns"]["common_requests"]
    return sorted(reqs.items(), key=lambda x: x[1], reverse=True)[:top_n]


def get_active_hours() -> str:
    mem = load_memory()
    hourly = mem["patterns"]["hourly"]
    if not hourly:
        return "нет данных"
    return f"{max(hourly, key=hourly.get)}:00"


def get_stats() -> dict:
    mem = load_memory()
    return {
        "session_count":      mem.get("session_count", 0),
        "total_interactions": mem.get("total_interactions", 0),
        "last_seen":          mem.get("last_seen"),
        "peak_hour":          get_active_hours(),
        "top_requests":       get_frequent_requests(3),
    }


def get_stats_summary() -> dict:
    return get_stats()


def get_absence_message() -> str:
    mem  = load_memory()
    last = mem.get("last_seen")
    if not last:
        return "первый запуск системы, сэр"
    try:
        diff = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return ""
    secs = diff.total_seconds()
    if secs < 1800:
        return ""
    if secs < 3600:
        return f"вы отсутствовали {int(secs/60)} минут"
    if diff.days == 0:
        return f"вы отсутствовали {int(secs/3600)} ч."
    return f"вы отсутствовали {diff.days} дней"


def get_greeting_context() -> str:
    mem   = load_memory()
    count = mem.get("session_count", 0)
    last  = mem.get("last_seen")
    if not last:
        return "первый запуск системы"
    try:
        diff = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return "система готова"
    if diff.total_seconds() < 3600 and diff.days == 0:
        return f"сессия продолжается, {count} взаимодействий"
    if diff.days == 0:
        return f"возвращение через {int(diff.total_seconds()/3600)} ч."
    return f"отсутствие {diff.days} дней"
