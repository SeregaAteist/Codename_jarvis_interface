"""JARVIS Notify — только отправка срочных уведомлений владельцу."""

from __future__ import annotations

from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
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


async def send_with_keyboard(
    text: str,
    buttons: list[list[tuple[str, str]]],
    parse_mode: str = "HTML",
) -> None:
    """Отправить сообщение с inline-клавиатурой.

    buttons: список строк, каждая строка — список (label, callback_data).
    Пример: [[("✅ Одобрить", "approve"), ("❌ Отклонить", "reject")]]
    """
    bot = get_notify_bot()
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=data) for label, data in row]
            for row in buttons
        ]
    )
    if bot._app is None:
        raise RuntimeError("[notify] bot.build() не был вызван")
    await bot._app.bot.send_message(
        chat_id=bot.owner_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


async def send_document(
    path: str | Path,
    caption: str = "",
    parse_mode: str = "HTML",
) -> None:
    """Отправить файл владельцу."""
    bot = get_notify_bot()
    if bot._app is None:
        raise RuntimeError("[notify] bot.build() не был вызван")
    with open(path, "rb") as f:
        await bot._app.bot.send_document(
            chat_id=bot.owner_id,
            document=InputFile(f, filename=Path(path).name),
            caption=caption or None,
            parse_mode=parse_mode if caption else None,
        )
