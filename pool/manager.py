"""Global API Key Pool — manages multiple keys per provider with quota tracking."""
from __future__ import annotations
import os
import re
import time
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "sqlite" / "api_pool.db"

PROVIDERS = ["gemini", "groq", "claude", "anthropic", "openai", "xai", "elevenlabs", "telegram"]


class APIPool:
    """Manages multiple API keys per provider. Tracks daily quota, cooldowns, errors."""

    def __init__(self):
        self._keys: dict[str, list[str]] = {}
        self._init_db()
        self._load_keys()

    def _init_db(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quota (
                    key_hash TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    used_today INTEGER DEFAULT 0,
                    date TEXT,
                    errors INTEGER DEFAULT 0,
                    last_used TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)

    def _load_keys(self):
        """Load all PROVIDER_KEY_N and PROVIDER_API_KEY_N from environment."""
        for provider in PROVIDERS:
            keys = []
            for fmt in [f"{provider.upper()}_API_KEY", f"{provider.upper()}_KEY"]:
                val = os.getenv(fmt, "").strip()
                if val and val not in keys:
                    keys.append(val)
            patterns = [
                re.compile(rf"^{provider.upper()}_KEY_(\d+)$"),
                re.compile(rf"^{provider.upper()}_API_KEY_(\d+)$"),
            ]
            numbered = {}
            for env_key, val in os.environ.items():
                for pat in patterns:
                    m = pat.match(env_key)
                    if m and val.strip():
                        numbered[int(m.group(1))] = val.strip()
            for idx in sorted(numbered):
                if numbered[idx] not in keys:
                    keys.append(numbered[idx])
            self._keys[provider] = keys
            if keys:
                logger.info("[Pool] %s: %d key(s) loaded", provider, len(keys))

    def get(self, provider: str) -> Optional[str]:
        """Return best available key (least used today). None if no keys."""
        if provider == "anthropic":
            provider = "claude"
        keys = self._keys.get(provider, [])
        if not keys:
            return None
        today = time.strftime("%Y-%m-%d")
        best_key, best_used = None, float("inf")
        for key in keys:
            rec = self._get_record(key, provider, today)
            if rec["status"] == "cooldown":
                continue
            if rec["used_today"] < best_used:
                best_used = rec["used_today"]
                best_key = key
        return best_key if best_key else keys[0]

    def report_success(self, provider: str, key: str):
        """Increment usage counter for key."""
        if provider == "anthropic":
            provider = "claude"
        today = time.strftime("%Y-%m-%d")
        key_hash = self._hash(key)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO quota (key_hash, provider, used_today, date, last_used, status)
                VALUES (?, ?, 1, ?, ?, 'active')
                ON CONFLICT(key_hash) DO UPDATE SET
                    used_today = CASE WHEN date = ? THEN used_today + 1 ELSE 1 END,
                    date = ?,
                    last_used = ?,
                    status = 'active'
            """, (key_hash, provider, today, time.strftime("%H:%M:%S"),
                  today, today, time.strftime("%H:%M:%S")))

    def report_quota_exceeded(self, provider: str, key: str):
        """Mark key as in cooldown (quota exhausted)."""
        if provider == "anthropic":
            provider = "claude"
        key_hash = self._hash(key)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO quota (key_hash, provider, status, errors)
                VALUES (?, ?, 'cooldown', 1)
                ON CONFLICT(key_hash) DO UPDATE SET
                    status = 'cooldown',
                    errors = errors + 1
            """, (key_hash, provider))
        logger.warning("[Pool] %s key quota exceeded → cooldown", provider)

    def report_error(self, provider: str, key: str):
        """Increment error counter without full cooldown."""
        if provider == "anthropic":
            provider = "claude"
        key_hash = self._hash(key)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO quota (key_hash, provider, errors)
                VALUES (?, ?, 1)
                ON CONFLICT(key_hash) DO UPDATE SET errors = errors + 1
            """, (key_hash, provider))

    def get_status(self) -> dict:
        """Return full status for all keys — for UI /connections endpoint."""
        today = time.strftime("%Y-%m-%d")
        result = {}
        for provider, keys in self._keys.items():
            if not keys:
                continue
            result[provider] = []
            for key in keys:
                rec = self._get_record(key, provider, today)
                result[provider].append({
                    "key_preview": key[:8] + "••••" + key[-4:] if len(key) > 12 else "••••",
                    "used_today": rec["used_today"],
                    "status": rec["status"],
                    "errors": rec["errors"],
                })
        return result

    def add_key(self, provider: str, key: str):
        """Dynamically add a key (from UI)."""
        if provider not in self._keys:
            self._keys[provider] = []
        if key not in self._keys[provider]:
            self._keys[provider].append(key)
            logger.info("[Pool] Added new key for %s", provider)

    def remove_key(self, provider: str, key: str):
        """Remove a key (from UI)."""
        if provider in self._keys and key in self._keys[provider]:
            self._keys[provider].remove(key)

    def _get_record(self, key: str, provider: str, today: str) -> dict:
        key_hash = self._hash(key)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT used_today, date, errors, status FROM quota WHERE key_hash=?",
                (key_hash,)
            ).fetchone()
        if not row:
            return {"used_today": 0, "date": today, "errors": 0, "status": "active"}
        used, date, errors, status = row
        if date != today:
            used, status = 0, "active"
        return {"used_today": used, "date": date, "errors": errors, "status": status}

    @staticmethod
    def _hash(key: str) -> str:
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()[:16]


# Singleton — import this everywhere
pool = APIPool()
