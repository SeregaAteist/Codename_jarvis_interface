"""Thread-safe two-tier cache (memory + disk) for Jarvis."""
from __future__ import annotations
import json
import os
import threading
import time

from core.config_paths import CACHE_DIR as _CACHE_DIR_PATH
_CACHE_DIR = str(_CACHE_DIR_PATH)
os.makedirs(_CACHE_DIR, exist_ok=True)


class Cache:
    """In-memory cache with optional disk fallback."""

    def __init__(self, ttl: int = 300, disk: bool = False):
        self.ttl   = ttl
        self._disk = disk
        self._mem: dict[str, tuple] = {}
        self._lock = threading.Lock()

    def _disk_path(self, key: str) -> str:
        safe = key.replace("/", "_").replace(":", "_")
        return os.path.join(_CACHE_DIR, f"{safe}.json")

    def get(self, key: str):
        now = time.monotonic()
        with self._lock:
            if key in self._mem:
                val, ts = self._mem[key]
                if now - ts < self.ttl:
                    return val
                del self._mem[key]

        if not self._disk:
            return None

        path = self._disk_path(key)
        try:
            if os.path.exists(path) and time.time() - os.path.getmtime(path) < self.ttl:
                with open(path, encoding="utf-8") as f:
                    val = json.load(f)
                with self._lock:
                    self._mem[key] = (val, now)
                return val
        except (OSError, json.JSONDecodeError):
            pass
        return None

    def set(self, key: str, value) -> None:
        now = time.monotonic()
        with self._lock:
            self._mem[key] = (value, now)

        if self._disk:
            path = self._disk_path(key)
            try:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(value, f, ensure_ascii=False)
                os.replace(tmp, path)
            except OSError:
                pass

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._mem.pop(key, None)
        if self._disk:
            try:
                os.unlink(self._disk_path(key))
            except OSError:
                pass

    def clear(self) -> None:
        with self._lock:
            self._mem.clear()


# ── Shared instances ──────────────────────────────────────────────────────────

weather_cache = Cache(ttl=600,  disk=True)   # 10 min
search_cache  = Cache(ttl=1800, disk=True)   # 30 min
metrics_cache = Cache(ttl=3,    disk=False)  # 3 sec
memory_cache  = Cache(ttl=5,    disk=False)  # 5 sec  (memory.json hot-reload)
