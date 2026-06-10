import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
TMP_DIR = BASE_DIR / "tmp"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "deferred.db"

TMP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID: int = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
TOPIC_ID: int = int(os.getenv("TOPIC_ID", "0"))
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

WHISPER_BIN: str = os.getenv(
    "WHISPER_BIN",
    str(Path.home() / "jarvis" / "voice" / "main"),
)
WHISPER_MODEL: str = os.getenv(
    "WHISPER_MODEL",
    str(Path.home() / "jarvis" / "voice" / "models" / "ggml-base.bin"),
)

CLAUDE_MODEL = "claude-sonnet-4-20250514"
BATCH_TIMEOUT = 30  # seconds to wait for more media after first item
