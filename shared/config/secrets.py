"""Слой секретов: загрузка .env ОДИН раз, fail-fast на обязательных.

Слой 2 из 3. Только секреты/окружение (токены, ключи). В git не попадает
ничего, кроме этого загрузчика — значения живут в корневом .env.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

from shared.config.base import ROOT

# Единая точка загрузки .env для всех ботов проекта.
load_dotenv(ROOT / ".env")


def req(key: str) -> str:
    """Обязательная переменная — иначе fail-fast."""
    val = os.getenv(key)
    if not val:
        raise RuntimeError(
            f"CONFIG FAIL-FAST: обязательная переменная {key} отсутствует в .env"
        )
    return val


def opt(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _collect(names: tuple[str, ...], numbered_prefix: str | None = None) -> list[str]:
    keys: list[str] = []
    for n in names:
        v = os.getenv(n, "").strip()
        if v and v not in keys:
            keys.append(v)
    if numbered_prefix:
        i = 1
        while True:
            v = os.getenv(f"{numbered_prefix}{i}", "").strip()
            if not v:
                break
            if v not in keys:
                keys.append(v)
            i += 1
    return keys


def gemini_keys() -> list[str]:
    """Пул ключей Gemini: список через запятую (GEMINI_KEYS) + одиночные + нумерованные."""
    keys = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
    for k in _collect(("GEMINI_API_KEY", "GEMINI_KEY"), "GEMINI_API_KEY_"):
        if k not in keys:
            keys.append(k)
    return keys


def claude_keys() -> list[str]:
    return _collect(("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"), "ANTHROPIC_API_KEY_")
