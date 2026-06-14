"""Inbox dispatcher — читает топик /2, создаёт задачи для watcher."""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

INBOX_CHAT_ID = int(os.getenv("INBOX_CHAT_ID") or os.getenv("RAFAIL_CHAT_ID") or 0)
INBOX_TOPIC_ID = int(os.getenv("INBOX_TOPIC_ID", "2"))
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "374728252"))
TASKS_DIR = Path(os.path.expanduser("~/Projects/jarvis/tasks/pending"))

_STATUS_TRIGGERS = {"джарвис, статус", "status", "what's up"}

# (prefix_variants) → agent name
_PREFIX_MAP: list[tuple[tuple[str, ...], str]] = [
    (("рафаил,", "rafail,"), "rafail"),
    (("джарвис,", "jarvis,"), "jarvis"),
]

# Префиксы других ботов — inbox_dispatcher их игнорирует
_OTHER_AGENT_PREFIXES = ("рафаил,", "rafail,", "аниме,", "anime,")


def _parse_prefix(text: str) -> tuple[str, str]:
    """Возвращает (agent, task_text). agent='general' если нет префикса."""
    low = text.lower()
    for prefixes, agent in _PREFIX_MAP:
        for p in prefixes:
            if low.startswith(p):
                return agent, text[len(p) :].strip()
    return "general", text


def _is_for_jarvis(text: str) -> bool:
    """True если сообщение адресовано Джарвису или без префикса (общая задача)."""
    text_lower = text.lower()
    if text_lower.startswith(("джарвис,", "jarvis,")):
        return True
    if any(text_lower.startswith(p) for p in _OTHER_AGENT_PREFIXES):
        return False
    return True  # без префикса — для Джарвиса


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


def _build_status_report() -> str:
    """Собрать статус всех jarvis-сервисов через launchctl."""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    try:
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=5
        )
        lines = {
            ln.split("\t")[2]: ln
            for ln in result.stdout.splitlines()
            if "jarvis" in ln and len(ln.split("\t")) >= 3
        }
    except Exception:
        lines = {}

    services = [
        ("com.jarvis.tg-media-analyzer", "tg-media-analyzer"),
        ("com.jarvis.rafail-bot", "rafail-bot"),
        ("com.jarvis.work-bot", "work-bot"),
        ("com.jarvis.ringostat", "ringostat"),
        ("com.jarvis.anime-monitor", "anime-monitor"),
        ("com.jarvis.task-watcher", "task-watcher"),
        ("com.jarvis.rafail-cron", "rafail-cron (scheduled)"),
        ("com.jarvis.morning-briefing", "morning-briefing (scheduled)"),
    ]

    rows = []
    for label, display in services:
        if label not in lines:
            rows.append(f"⚫ {display}")
        elif "\t0\t" in lines[label]:
            rows.append(f"✅ {display}")
        else:
            rows.append(f"⚠️ {display}")

    services_block = "\n".join(rows)

    # Быстрая статистика из доступных источников
    stats: list[str] = []
    try:
        import sys

        sys.path.insert(0, os.path.expanduser("~/Projects/jarvis"))
        from modules.rafail.db import connect

        with connect() as c:
            materials = c.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
        stats.append(f"• Рафаіл: {materials} матеріалів в базі")
    except Exception:
        pass

    calls_dir = Path(os.path.expanduser("~/Projects/jarvis/data/calls"))
    if calls_dir.exists():
        stats.append(f"• Дзвінки: {len(list(calls_dir.glob('*.mp3')))} записів")

    try:
        sys_path = os.path.expanduser("~/Projects/jarvis/modules/anime-monitor")
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from agents.db_agent import get_all_snapshot  # type: ignore[import]

        stats.append(f"• Аніме: {len(get_all_snapshot())} тайтлів в каталозі")
    except Exception:
        pass

    stats_block = "\n".join(stats) if stats else "• статистика недоступна"

    return (
        f"🤖 JARVIS статус [{now}]\n\n"
        f"{services_block}\n\n"
        f"📊 Зараз:\n{stats_block}"
    )


async def dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений из inbox-топика /2."""
    msg = update.message
    if not msg or msg.message_thread_id != INBOX_TOPIC_ID:
        return
    if not update.effective_user or update.effective_user.id != OWNER_USER_ID:
        return

    text = msg.text or ""

    if text.lower().strip() in _STATUS_TRIGGERS:
        logger.info("[inbox] запит статусу")
        report = _build_status_report()
        await context.bot.send_message(
            chat_id=INBOX_CHAT_ID,
            message_thread_id=INBOX_TOPIC_ID,
            text=report,
        )
        return

    if not _is_for_jarvis(text):
        return  # сообщение для другого бота — молчим

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

    from shared.logging_setup import setup_logging

    setup_logging("~/Projects/jarvis/logs/inbox-bot.log")

    from shared.config.settings import get_settings

    s = get_settings()
    token = s.jarvis_work_bot_token or s.telegram_bot_token
    if not token:
        print("ERROR: нет токена бота (JARVIS_WORK_BOT_TOKEN / TELEGRAM_BOT_TOKEN)")
        sys.exit(1)

    print(f"[inbox] запуск на токене {token[:10]}...")
    app = create_inbox_app(token)
    app.run_polling(allowed_updates=["message"])
