"""JARVIS Notify — только отправка срочных уведомлений владельцу."""

from __future__ import annotations

from telegram.ext import Application

from modules.bots.base_bot import JarvisBot
from shared.config.settings import get_settings


class NotifyBot(JarvisBot):
    """Бот для срочных уведомлений владельцу — только отправка, без polling."""

    def __init__(self) -> None:
        s = get_settings()
        token = s.jarvis_notify_bot_token or s.telegram_bot_token
        super().__init__(token=token, name="notify")

    def register_handlers(self, app: Application) -> None:  # type: ignore[type-arg]
        pass  # notify-бот не принимает команды


# синглтон
_notify: NotifyBot | None = None


def get_notify_bot() -> NotifyBot:
    global _notify
    if _notify is None:
        _notify = NotifyBot()
        _notify.build()
    return _notify


async def send_urgent(text: str, parse_mode: str = "HTML") -> None:
    """Отправить срочное уведомление владельцу."""
    bot = get_notify_bot()
    await bot.send_message(bot.owner_id, text, parse_mode=parse_mode)
