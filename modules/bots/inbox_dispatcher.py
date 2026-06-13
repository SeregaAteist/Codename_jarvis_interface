"""Inbox dispatcher — читает топик /2, создаёт задачи для watcher."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

INBOX_CHAT_ID = int(os.getenv("INBOX_CHAT_ID") or os.getenv("RAFAIL_CHAT_ID") or 0)
INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID", "2"))
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "374728252"))
TASKS_DIR = Path(os.path.expanduser("~/Projects/jarvis/tasks/pending"))

# (prefix_variants) → agent name
_PREFIX_MAP: list[tuple[tuple[str, ...], str]] = [
    (("рафаил,", "rafail,"), "rafail"),
    (("джарвис,", "jarvis,"), "jarvis"),
]


def _parse_prefix(text: str) -> tuple[str, str]:
    """Возвращает (agent, task_text). agent='general' если нет префикса."""
    low = text.lower()
    for prefixes, agent in _PREFIX_MAP:
        for p in prefixes:
            if low.startswith(p):
                return agent, text[len(p) :].strip()
    return "general", text


def _create_task_file(agent: str, task_text: str) -> Path:
    task_id = f"TASK_tg_{datetime.now().strftime('%H%M%S')}"
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    path = TASKS_DIR / f"{task_id}.md"
    path.write_text(
        f"# {task_id}\n"
        f"## Источник: Telegram топик /2\n"
        f"## Агент: {agent}\n"
        f"## Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"## ЗАДАЧА\n{task_text}\n\n"
        f"## ПОСЛЕ ВЫПОЛНЕНИЯ\n"
        f"Отправить результат в Telegram:\n"
        f"CHAT_ID: {INBOX_CHAT_ID}\n"
        f"TOPIC_ID: {INBOX_TOPIC_ID}\n"
        f"Формат: краткий отчёт что сделано\n"
    )
    return path


async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений из inbox-топика /2."""
    msg = update.message
    if not msg or msg.message_thread_id != INBOX_TOPIC_ID:
        return
    if not update.effective_user or update.effective_user.id != OWNER_USER_ID:
        return

    text = msg.text or ""
    logger.info("[inbox] сообщение: %s", text[:100])

    agent, task_text = _parse_prefix(text)
    task_path = _create_task_file(agent, task_text)
    task_id = task_path.stem

    await context.bot.send_message(
        chat_id=INBOX_CHAT_ID,
        message_thread_id=INBOX_TOPIC_ID,
        text=f"✅ Задача принята: {task_id}\n⏳ Watcher подхватит через ~30 сек",
    )


async def handle_inbox_voice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Голосовые в топике /2 → транскрипция → создать задачу."""
    msg = update.message
    if not msg or msg.message_thread_id != INBOX_TOPIC_ID:
        return
    if not update.effective_user or update.effective_user.id != OWNER_USER_ID:
        return

    from modules.bots.voice_handler import transcribe_voice

    await context.bot.send_message(
        chat_id=INBOX_CHAT_ID,
        message_thread_id=INBOX_TOPIC_ID,
        text="🎙 Транскрибирую...",
    )
    text = await transcribe_voice(msg.voice.file_id, context.bot.token)
    if not text:
        await context.bot.send_message(
            chat_id=INBOX_CHAT_ID,
            message_thread_id=INBOX_TOPIC_ID,
            text="❌ Не удалось распознать голосовое сообщение",
        )
        return

    await context.bot.send_message(
        chat_id=INBOX_CHAT_ID,
        message_thread_id=INBOX_TOPIC_ID,
        text=f"📝 Распознано: {text}",
    )
    msg.text = text
    await dispatch(update, context)


def create_inbox_app(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch))
    app.add_handler(MessageHandler(filters.VOICE, handle_inbox_voice))
    return app


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.expanduser("~/Projects/jarvis"))
    from dotenv import load_dotenv

    load_dotenv(os.path.expanduser("~/Projects/jarvis/.env"))

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

    from shared.config.settings import get_settings

    s = get_settings()
    token = s.jarvis_work_bot_token or s.telegram_bot_token
    if not token:
        print("ERROR: нет токена бота (JARVIS_WORK_BOT_TOKEN / TELEGRAM_BOT_TOKEN)")
        sys.exit(1)

    print(f"[inbox] запуск на токене {token[:10]}...")
    app = create_inbox_app(token)
    app.run_polling(allowed_updates=["message"])
