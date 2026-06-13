#!/usr/bin/env python3
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from bot import anime_menu, rafail_menu
from bot.handlers import handle_callback, handle_media, handle_url
from bot.supervisor_bridge import handle_supervisor_callback, setup_supervisor
from bot.task_handler import handle_manual_task, handle_task_callback
from db.storage import init_db
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from shared.logging_setup import setup_logging

# S-1/S-2: маскировка токена/ключей + httpx→WARNING + ротация 10MB×5.
setup_logging(Path(__file__).parent / "logs" / "bot.log", console=False)
logger = logging.getLogger(__name__)

_INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID", "2"))


def _is_inbox(update) -> bool:
    msg = update.effective_message
    return bool(msg and msg.message_thread_id == _INBOX_TOPIC_ID)


async def _route_text(update, context):
    """Текст: сперва состояния меню (аниме, рафаил), иначе — задачи."""
    if _is_inbox(update):
        return  # топик /2 — media-analyzer молчит
    if await anime_menu.handle_text_state(update, context):
        return
    if await rafail_menu.handle_text_state(update, context):
        return
    await handle_manual_task(update, context)


async def _open_anime_menu(update, context):
    if _is_inbox(update):
        return
    await anime_menu.open_menu(update, context)


async def _open_rafail_menu(update, context):
    if _is_inbox(update):
        return
    await rafail_menu.open_menu(update, context)


def build_app() -> Application:
    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")
    config.require_security_ids()  # fail fast: TELEGRAM_CHAT_ID + OWNER_USER_ID обязательны

    init_db()
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Media files
    media_filter = filters.VIDEO | filters.PHOTO | filters.VOICE | filters.VIDEO_NOTE
    app.add_handler(MessageHandler(media_filter, handle_media))

    # URLs
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("url"), handle_url))

    # Меню по ключевым словам («аниме», «рафаил»), текст-состояния — ПЕРЕД задачами
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"(?i)^аниме$"), _open_anime_menu)
    )
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"(?i)^рафаил$"), _open_rafail_menu)
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _route_text))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^[sdx]:"))
    app.add_handler(
        CallbackQueryHandler(handle_task_callback, pattern=r"^(approve|cancel):")
    )
    app.add_handler(
        CallbackQueryHandler(handle_supervisor_callback, pattern=r"^sup_(ok|no):")
    )
    app.add_handler(CallbackQueryHandler(anime_menu.handle_callback, pattern=r"^an:"))
    app.add_handler(CallbackQueryHandler(rafail_menu.handle_callback, pattern=r"^rf:"))
    app.add_handler(
        CallbackQueryHandler(rafail_menu.handle_approval_callback, pattern=r"^rfap:")
    )

    # Капитан: approve_callback на TG-кнопках + уведомления о результате
    setup_supervisor(app)

    # AnimeAgent: уведомления о сериях в TG + регистрация в реестре
    import core.registry as registry
    from agents.anime import AnimeAgent

    async def _anime_notify(text: str, url: str | None) -> None:
        await anime_menu.notify_episode(app, text, url)

    registry.register(AnimeAgent(notify_func=_anime_notify))

    # Рафаил: агент + TG-approver + меню
    rafail_menu.setup_rafail(app)

    return app


def main():
    logger.info("=== tg-media-analyzer starting ===")
    logger.info(
        "Gemini keys: %d | Claude keys: %d | Tasks topic: %d | Owner: %d",
        len(config.GEMINI_KEYS),
        len(config.CLAUDE_KEYS),
        config.TASKS_TOPIC_ID,
        config.OWNER_USER_ID,
    )
    app = (
        build_app()
    )  # бросит RuntimeError, если не заданы обязательные ID безопасности
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
