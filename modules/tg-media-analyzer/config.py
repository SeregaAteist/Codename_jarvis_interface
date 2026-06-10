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

# Единственный пользователь, которому разрешено управлять ботом и ставить
# задачи Claude Code (RCE-уровень доступа). 0 = не задан → бот закрыт.
OWNER_USER_ID: int = int(os.getenv("OWNER_USER_ID", "0"))


def require_security_ids() -> None:
    """Fail fast if mandatory security IDs are missing."""
    if TELEGRAM_CHAT_ID == 0 or OWNER_USER_ID == 0:
        raise RuntimeError(
            "Заданы не все обязательные ID безопасности: "
            "TELEGRAM_CHAT_ID и OWNER_USER_ID должны быть указаны в .env"
        )


_PLACEHOLDERS = {"your_key_here", "your_second_key_here", "your_token_here", ""}


def _load_keys(prefix: str) -> list[str]:
    keys = []
    for fmt in [f"{prefix}_API_KEY", f"{prefix}_KEY"]:
        v = os.getenv(fmt, "").strip()
        if v and v not in keys and v not in _PLACEHOLDERS:
            keys.append(v)
    numbered = {}
    for k, v in os.environ.items():
        m = re.match(rf"^{prefix}_(?:API_)?KEY_(\d+)$", k)
        if m and v.strip() and v.strip() not in _PLACEHOLDERS:
            numbered[int(m.group(1))] = v.strip()
    for idx in sorted(numbered):
        if numbered[idx] not in keys:
            keys.append(numbered[idx])
    return keys


GEMINI_KEYS: list[str] = _load_keys("GEMINI")
CLAUDE_KEYS: list[str] = _load_keys("ANTHROPIC") or _load_keys("CLAUDE")

GEMINI_MODEL = "gemini-2.5-flash"
CLAUDE_MODEL = "claude-fable-5"
BATCH_TIMEOUT = 3
MAX_IMAGE_SIZE = 4 * 1024 * 1024

# Топик для задач Claude Code
TASKS_TOPIC_ID: int = int(os.getenv("TASKS_TOPIC_ID", "0"))

# SSH настройки
SSH_HOST = "100.84.234.120"
SSH_KEY  = "/Users/seregaateist/.ssh/jarvis_bot"
