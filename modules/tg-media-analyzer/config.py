import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load from project root .env
_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")

BASE_DIR = Path(__file__).parent
TMP_DIR = BASE_DIR / "tmp"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "media_analyzer.db"
TMP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: int = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
TOPIC_ID: int = int(os.getenv("TOPIC_ID", "0"))


def _load_keys(prefix: str) -> list[str]:
    keys = []
    for fmt in [f"{prefix}_API_KEY", f"{prefix}_KEY"]:
        v = os.getenv(fmt, "").strip()
        if v and v not in keys:
            keys.append(v)
    numbered = {}
    for k, v in os.environ.items():
        m = re.match(rf"^{prefix}_(?:API_)?KEY_(\d+)$", k)
        if m and v.strip():
            numbered[int(m.group(1))] = v.strip()
    for idx in sorted(numbered):
        if numbered[idx] not in keys:
            keys.append(numbered[idx])
    return keys


GEMINI_KEYS: list[str] = _load_keys("GEMINI")
CLAUDE_KEYS: list[str] = _load_keys("ANTHROPIC") or _load_keys("CLAUDE")

GEMINI_MODEL = "gemini-2.5-flash"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
BATCH_TIMEOUT = 30
MAX_IMAGE_SIZE = 4 * 1024 * 1024
