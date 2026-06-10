import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    BASE_URL: str = "https://animevost.org"
    PAGES_TO_SCAN: int = 3
    SCAN_HOURS: List[int] = field(
        default_factory=lambda: [int(h) for h in __import__("os").getenv("SCAN_HOURS", "4").split(",")]
    )
    DB_PATH: str = "data/anime.db"
    REPORTS_DIR: str = "reports"
    REQUEST_DELAY: float = 1.5
    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")
    OLLAMA_URL: str = "http://localhost:11434"
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    GROUP_CHAT_ID: str = os.getenv("GROUP_CHAT_ID", "")
    THREAD_ID: int = int(os.getenv("THREAD_ID", "0"))
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    JIKAN_URL: str = "https://api.jikan.moe/v4"

cfg = Config()
