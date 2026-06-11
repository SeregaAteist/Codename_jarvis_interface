"""Тонкая обёртка над слоистым shared.config — для обратной совместимости.

Единый источник правды теперь в shared/config/ (base + secrets + modules/media_analyzer.yaml).
Здесь только реэкспорт старых имён, чтобы существующие импорты `import config`
продолжали работать без правок. Никаких hardcoded значений (пути/хосты/модели)
здесь нет — всё приходит из CFG.
"""
from __future__ import annotations

from pathlib import Path

from shared.config import CFG  # слоистый конфиг media_analyzer (грузится один раз)

# --- Каталоги, специфичные ИМЕННО для этого бота (не глобальный конфиг) ---
BASE_DIR = Path(__file__).parent
TMP_DIR = BASE_DIR / "tmp"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "media_analyzer.db"
TMP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# --- Реэкспорт из единого CFG (старые имена для совместимости) ---
TELEGRAM_TOKEN = CFG.TELEGRAM_TOKEN
TELEGRAM_CHAT_ID = CFG.TELEGRAM_CHAT_ID
TOPIC_ID = CFG.TOPIC_ID
OWNER_USER_ID = CFG.OWNER_USER_ID
TASKS_TOPIC_ID = CFG.TASKS_TOPIC_ID

GEMINI_KEYS = CFG.GEMINI_KEYS
CLAUDE_KEYS = CFG.CLAUDE_KEYS
GEMINI_MODEL = CFG.GEMINI_MODEL
CLAUDE_MODEL = CFG.CLAUDE_MODEL

BATCH_TIMEOUT = CFG.BATCH_TIMEOUT
MAX_IMAGE_SIZE = CFG.MAX_IMAGE_SIZE


def require_security_ids() -> None:
    """Совместимость: fail-fast по обязательным ID безопасности (делегирует в CFG)."""
    CFG.require_security_ids()
