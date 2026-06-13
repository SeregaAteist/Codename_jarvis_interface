"""Базовый класс для всех Telegram-ботов JARVIS."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from telegram.ext import Application

from shared.config.settings import JarvisSettings, get_settings

logger = logging.getLogger(__name__)


class JarvisBot(ABC):
    """Базовый класс для всех ботов JARVIS."""

    def __init__(self, token: str, name: str) -> None:
        self._token = token
        self._name = name
        self._app: Application | None = None  # type: ignore[type-arg]
        self._settings: JarvisSettings = get_settings()

    @property
    def owner_id(self) -> int:
        return self._settings.owner_user_id

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id

    @abstractmethod
    def register_handlers(self, app: Application) -> None:  # type: ignore[type-arg]
        """Зарегистрировать handlers в приложении."""

    def build(self) -> Application:  # type: ignore[type-arg]
        app: Application = Application.builder().token(self._token).build()  # type: ignore[type-arg]
        self.register_handlers(app)
        self._app = app
        return app

    def run(self) -> None:
        logger.info("[%s] запуск", self._name)
        app = self.build()
        app.run_polling(allowed_updates=["message", "callback_query"])

    async def send_message(
        self,
        chat_id: int,
        text: str,
        thread_id: int | None = None,
        parse_mode: str = "HTML",
    ) -> None:
        if self._app is None:
            raise RuntimeError(f"[{self._name}] bot.build() не был вызван")
        kwargs: dict[str, object] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if thread_id is not None:
            kwargs["message_thread_id"] = thread_id
        await self._app.bot.send_message(**kwargs)
