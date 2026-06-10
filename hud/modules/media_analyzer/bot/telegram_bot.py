"""Telegram bot: batch media collection, transcription, Claude analysis."""

import asyncio
import logging
import uuid
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from agents.analyzer import analyze_media, generate_implementation
from agents.db_agent import init_db, save_deferred
from agents.transcriber import extract_audio, transcribe

logger = logging.getLogger(__name__)

# Batch state keyed by (chat_id, thread_id)
_batches: dict[tuple, list[dict]] = {}
_batch_tasks: dict[tuple, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

async def _process_batch(key: tuple, items: list[dict], app: Application) -> None:
    chat_id, thread_id = key

    status = None
    try:
        status = await app.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=f"⏳ Обрабатываю {len(items)} медиафайл(ов)...",
        )
    except Exception as e:
        logger.warning("Не удалось отправить статус: %s", e)

    transcripts: list[str] = []
    image_paths: list[Path] = []
    media_paths: list[str] = []

    for item in items:
        try:
            tg_file = await app.bot.get_file(item["file_id"])
            suffix = {"video": ".mp4", "voice": ".ogg", "photo": ".jpg"}[item["type"]]
            local_path = config.TMP_DIR / f"{uuid.uuid4().hex}{suffix}"
            await tg_file.download_to_drive(local_path)
            media_paths.append(str(local_path))

            if item["type"] == "photo":
                image_paths.append(local_path)
            else:
                audio_path = local_path
                if item["type"] == "video":
                    try:
                        audio_path = await extract_audio(local_path)
                    except Exception as e:
                        logger.warning("Извлечение аудио не удалось: %s", e)

                try:
                    text = await transcribe(audio_path)
                    if text:
                        transcripts.append(text)
                except Exception as e:
                    logger.error("Транскрипция не удалась: %s", e)
                    transcripts.append(f"[Ошибка транскрипции: {e}]")
        except Exception as e:
            logger.error("Ошибка обработки медиа: %s", e)

    # Claude analysis
    try:
        analysis = await analyze_media(transcripts, image_paths)
    except Exception as e:
        logger.error("Ошибка анализа: %s", e)
        analysis = f"Ошибка анализа: {e}"

    # Build reply
    transcript_section = "\n".join(transcripts) if transcripts else "—"
    reply = (
        f"📝 *ТРАНСКРИПЦИЯ:*\n{transcript_section}\n\n"
        f"🔍 *АНАЛИЗ:*\n{analysis}"
    )
    if len(reply) > 4000:
        reply = reply[:3990] + "\n_...[обрезано]_"

    # Store for callbacks — key is 32-char hex, callback_data ≤ 34 chars
    store_key = uuid.uuid4().hex
    app.bot_data.setdefault("analyses", {})[store_key] = {
        "title": (transcripts[0][:80] if transcripts else f"Медиа — {len(items)} файл(ов)"),
        "analysis": analysis,
        "media_paths": media_paths,
    }

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🚀 Приступить", callback_data=f"s:{store_key}"),
        InlineKeyboardButton("📌 Отложить",   callback_data=f"d:{store_key}"),
        InlineKeyboardButton("❌ Не интересно", callback_data=f"x:{store_key}"),
    ]])

    if status:
        try:
            await status.delete()
        except Exception:
            pass

    await app.bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=reply,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    # Cleanup tmp files — analysis text is what matters, paths are ephemeral
    for p in media_paths:
        path = Path(p)
        path.unlink(missing_ok=True)
        path.with_suffix(".wav").unlink(missing_ok=True)

    _batches.pop(key, None)
    _batch_tasks.pop(key, None)


async def _batch_timer(key: tuple, app: Application) -> None:
    try:
        await asyncio.sleep(config.BATCH_TIMEOUT)
        items = list(_batches.get(key, []))
        if items:
            await _process_batch(key, items, app)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Ошибка батч-таймера: %s", e, exc_info=True)
        _batches.pop(key, None)
        _batch_tasks.pop(key, None)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return

    # Topic and chat filter (checked in handler to allow flexible .env defaults)
    if config.TELEGRAM_CHAT_ID and msg.chat_id != config.TELEGRAM_CHAT_ID:
        return
    if config.TOPIC_ID and msg.message_thread_id != config.TOPIC_ID:
        return

    if msg.video:
        item = {"type": "video", "file_id": msg.video.file_id}
    elif msg.photo:
        item = {"type": "photo", "file_id": msg.photo[-1].file_id}
    elif msg.voice:
        item = {"type": "voice", "file_id": msg.voice.file_id}
    elif msg.video_note:
        item = {"type": "video", "file_id": msg.video_note.file_id}
    else:
        return

    key = (msg.chat_id, msg.message_thread_id)

    if key not in _batches:
        _batches[key] = []
        _batch_tasks[key] = asyncio.create_task(_batch_timer(key, context.application))

    _batches[key].append(item)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    raw = query.data or ""
    if ":" not in raw:
        return

    action, store_key = raw.split(":", 1)
    analyses: dict = context.bot_data.get("analyses", {})
    entry = analyses.get(store_key)

    # ❌ Не интересно
    if action == "x":
        await query.message.delete()
        return

    if not entry:
        await query.answer("Данные не найдены — бот был перезапущен.", show_alert=True)
        return

    # 📌 Отложить
    if action == "d":
        save_deferred(
            title=entry["title"],
            analysis=entry["analysis"],
            media_path=entry["media_paths"][0] if entry["media_paths"] else None,
        )
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            message_thread_id=query.message.message_thread_id,
            text="📌 Сохранено в отложенный пул.",
        )

    # 🚀 Приступить
    elif action == "s":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_chat_action(
            chat_id=query.message.chat_id, action="typing"
        )

        try:
            instructions = await generate_implementation(entry["analysis"])
        except Exception as e:
            instructions = f"Ошибка генерации инструкций: {e}"

        # Send with chunk splitting for long responses
        header = "🚀 *ИНСТРУКЦИИ ПО РЕАЛИЗАЦИИ:*\n\n"
        chunks = _split_text(header + instructions, max_len=4000)
        for chunk in chunks:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                message_thread_id=query.message.message_thread_id,
                text=chunk,
                parse_mode="Markdown",
            )


def _split_text(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        parts.append(text[:max_len])
        text = text[max_len:]
    return parts


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def build_app() -> Application:
    if not config.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не задан в .env")
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY не задан в .env")

    init_db()

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    media_filter = filters.VIDEO | filters.PHOTO | filters.VOICE | filters.VIDEO_NOTE
    app.add_handler(MessageHandler(media_filter, handle_media))
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^[sdx]:"))

    return app
