import os
import sys

import pytest

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from config import cfg  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Изолированная SQLite-БД на каждый тест."""
    db_path = str(tmp_path / "anime_test.db")
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    from agents.db_agent import init_db
    init_db()
    return db_path


@pytest.fixture
def sample_items():
    return [
        {
            "title": "Тестовое аниме / Test Anime [1-12 из 12]",
            "url": "https://animevost.org/tip/tv/1-test.html",
            "img_url": "https://animevost.org/img/1.jpg",
            "episode": "12 из 12",
            "rating": "9.1",
            "genres": "фэнтези, приключения",
        },
        {
            "title": "Второе аниме / Second Anime [5 из 24]",
            "url": "https://animevost.org/tip/tv/2-second.html",
            "img_url": "",
            "episode": "5 из 24",
            "rating": "",
            "genres": "",
        },
    ]


@pytest.fixture
def sent_messages(monkeypatch):
    """Перехват send_message агента уведомлений."""
    sent: list[str] = []

    async def fake_send(text: str, parse_mode: str = "HTML") -> bool:
        sent.append(text)
        return True

    import agents.notify_agent as notify_agent
    monkeypatch.setattr(notify_agent, "send_message", fake_send)
    return sent
