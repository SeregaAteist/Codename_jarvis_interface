"""Unit-тесты для AnimeBot."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def bot():
    with patch.dict(
        "os.environ", {"TELEGRAM_TOKEN": "test:token", "ANIME_TOPIC_ID": "100"}
    ):
        # перезагружаем cfg с тестовым токеном
        import importlib

        import config as cfg_module

        importlib.reload(cfg_module)

        from bot.telegram_bot import AnimeBot

        with patch.object(AnimeBot, "__init__", lambda self: None):
            instance = AnimeBot.__new__(AnimeBot)
            instance._token = "test:token"
            instance._name = "anime"
            instance._app = None
            # owner_user_id через _settings
            from shared.config.settings import JarvisSettings

            instance._settings = MagicMock(spec=JarvisSettings)
            instance._settings.owner_user_id = 374728252
        return instance


def test_is_owner_true(bot):
    assert bot.is_owner(374728252) is True


def test_is_owner_false(bot):
    assert bot.is_owner(999999) is False


def test_in_my_topic_anime_topic(bot):
    with patch.dict("os.environ", {"ANIME_TOPIC_ID": "100"}):
        import importlib

        import config as cfg_module

        importlib.reload(cfg_module)

        msg = MagicMock()
        msg.chat.type = "group"
        msg.message_thread_id = 100
        msg.text = "тест"

        # Проверяем через новый экземпляр с перезагруженным cfg
        assert bot._in_my_topic(msg) is True


def test_in_my_topic_private(bot):
    msg = MagicMock()
    msg.chat.type = "private"
    msg.message_thread_id = None
    msg.text = ""
    assert bot._in_my_topic(msg) is True


def test_in_my_topic_inbox_with_anime_prefix(bot):
    msg = MagicMock()
    msg.chat.type = "supergroup"
    msg.message_thread_id = 2
    msg.text = "Аниме, привет"
    assert bot._in_my_topic(msg) is True


def test_in_my_topic_inbox_lowercase_prefix(bot):
    msg = MagicMock()
    msg.chat.type = "supergroup"
    msg.message_thread_id = 2
    msg.text = "аниме, что посмотреть?"
    assert bot._in_my_topic(msg) is True


def test_in_my_topic_inbox_without_prefix(bot):
    msg = MagicMock()
    msg.chat.type = "supergroup"
    msg.message_thread_id = 2
    msg.text = "просто текст без префикса"
    assert bot._in_my_topic(msg) is False


def test_in_my_topic_wrong_topic(bot):
    msg = MagicMock()
    msg.chat.type = "supergroup"
    msg.message_thread_id = 202
    msg.text = "текст"
    assert bot._in_my_topic(msg) is False
