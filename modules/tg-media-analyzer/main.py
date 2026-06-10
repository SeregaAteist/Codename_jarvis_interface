#!/usr/bin/env python3
"""tg-media-analyzer — Telegram bot for media analysis with JARVIS integration."""
import logging
import sys
from pathlib import Path

# Ensure module root is in path
sys.path.insert(0, str(Path(__file__).parent))

from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

import config
from bot.handlers import handle_media, handle_callback
from db.storage import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")
    if not config.GEMINI_KEYS and not config.CLAUDE_KEYS:
        raise ValueError("Нет API ключей — добавьте GEMINI_API_KEY или ANTHROPIC_API_KEY в .env")

    init_db()
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    media_filter = filters.VIDEO | filters.PHOTO | filters.VOICE | filters.VIDEO_NOTE
    app.add_handler(MessageHandler(media_filter, handle_media))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^[sdx]:"))
    return app


def main():
    logger.info("=== tg-media-analyzer starting ===")
    logger.info("Gemini keys: %d | Claude keys: %d",
                len(config.GEMINI_KEYS), len(config.CLAUDE_KEYS))
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
