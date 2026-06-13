import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(MODULE_DIR, ".env"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class Config:
    BASE_URL: str = "https://animevost.org"
    PAGES_TO_SCAN: int = 3
    SCAN_HOURS: list[int] = field(
        default_factory=lambda: [
            int(h) for h in os.getenv("SCAN_HOURS", "4").split(",")
        ]
    )
    DB_PATH: str = os.path.join(MODULE_DIR, "data", "anime.db")
    REPORTS_DIR: str = os.path.join(MODULE_DIR, "reports")
    REQUEST_DELAY: float = 1.5
    USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    OWNER_USER_ID: int = int(os.getenv("OWNER_USER_ID", "0"))
    GROUP_CHAT_ID: str = os.getenv("GROUP_CHAT_ID", "")
    ANIME_TOPIC_ID: int = int(os.getenv("ANIME_TOPIC_ID", "0"))
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    JIKAN_URL: str = "https://api.jikan.moe/v4"
    # Агенты обогащения: имена через запятую, порядок не важен (priority в классах).
    ENRICHERS_ENABLED: list[str] = field(
        default_factory=lambda: [
            e.strip()
            for e in os.getenv("ENRICHERS_ENABLED", "anilist,jikan").split(",")
            if e.strip()
        ]
    )
    # Параллелизм запросов к внешним API (rate limit держим паузой между батчами).
    ENRICH_BATCH_SIZE: int = 3
    ANILIST_BATCH_PAUSE: float = 2.1  # ~1.4 req/sec (лимит AniList 90/мин)
    JIKAN_BATCH_PAUSE: float = 1.2  # лимит Jikan 3 req/sec


cfg = Config()
