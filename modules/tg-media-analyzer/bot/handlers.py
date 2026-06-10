from __future__ import annotations
import asyncio
import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

import config
from analyzers.batcher import smart_batch
from analyzers.video import extract_audio, extract_frames, transcribe
from bot.keyboards import action_keyboard
from db.storage import init_db, save_deferred
from pipeline.quick import quick_analyze
from pipeline.deep import deep_analyze

logger = logging.getLogger(__name__)

_batches: dict[tuple, list[dict]] = {}
_batch_tasks: dict[tuple, asyncio.Task] = {}


async def _process_batch(key: tuple, items: list[dict], app) -> None:
    chat_id, thread_id = key
    batches = smart_batch(items)

    for batch in batches:
        status_msg = None
        try:
            status_msg = await app.bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=f"⏳ Анализирую {len(batch.items)} файл(ов)...",
            )
        except Exception as e:
            logger.warning("Cannot send status: %s", e)

        transcripts: list[str] = []
        image_paths: list[Path] = []
        media_paths: list[str] = []
        reply_to_message_id: int | None = None

        for item in batch.items:
            try:
                tg_file = await app.bot.get_file(item["file_id"])
                suffix = {"video": ".mp4", "voice": ".ogg", "photo": ".jpg",
                          "video_note": ".mp4"}.get(item["type"], ".bin")
                local_path = config.TMP_DIR / f"{uuid.uuid4().hex}{suffix}"
                await tg_file.download_to_drive(local_path)
                media_paths.append(str(local_path))

                if item["type"] == "photo":
                    image_paths.append(local_path)

                elif item["type"] in ("video", "video_note"):
                    # Извлечь фреймы для vision анализа
                    frames = await extract_frames(local_path, n=4)
                    image_paths.extend(frames)
                    # Попробовать транскрипцию
                    try:
                        audio_path = await extract_audio(local_path)
                        text = await transcribe(audio_path)
                        if text:
                            transcripts.append(text)
                    except Exception as e:
                        logger.warning("Audio processing failed: %s", e)

                elif item["type"] == "voice":
                    try:
                        text = await transcribe(local_path)
                        if text:
                            transcripts.append(text)
                    except Exception as e:
                        logger.warning("Voice transcribe failed: %s", e)

                if "message_id" in item and reply_to_message_id is None:
                    reply_to_message_id = item["message_id"]

            except Exception as e:
                logger.error("Media processing error: %s", e)

        # Quick analysis (Gemini Vision)
        try:
            quick = await quick_analyze(image_paths, transcripts)
        except Exception as e:
            quick = f"⚠️ Ошибка анализа: {e}"

        transcript_section = "\n".join(transcripts) if transcripts else "—"
        reply = f"📝 *Транскрипция:*\n{transcript_section}\n\n🔍 *Анализ:*\n{quick}"
        if len(reply) > 4000:
            reply = reply[:3990] + "\n_...[обрезано]_"

        store_key = uuid.uuid4().hex
        app.bot_data.setdefault("analyses", {})[store_key] = {
            "title": transcripts[0][:80] if transcripts else f"Медиа — {len(batch.items)} файл(ов)",
            "quick": quick,
            "image_paths": [str(p) for p in image_paths],
            "transcripts": transcripts,
            "media_paths": media_paths,
        }

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        await app.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=reply,
            parse_mode="Markdown",
            reply_markup=action_keyboard(store_key),
            reply_to_message_id=reply_to_message_id,
        )

        for p in media_paths:
            path = Path(p)
            path.unlink(missing_ok=True)
            path.with_suffix(".wav").unlink(missing_ok=True)

    _batches.pop(key, None)
    _batch_tasks.pop(key, None)


async def _batch_timer(key: tuple, app) -> None:
    try:
        await asyncio.sleep(config.BATCH_TIMEOUT)
        items = list(_batches.get(key, []))
        if items:
            await _process_batch(key, items, app)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Batch timer error: %s", e, exc_info=True)
        _batches.pop(key, None)
        _batch_tasks.pop(key, None)


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return
    if not msg.from_user or msg.from_user.id != config.OWNER_USER_ID:
        return
    if config.TELEGRAM_CHAT_ID and msg.chat_id != config.TELEGRAM_CHAT_ID:
        return
    if config.TOPIC_ID and msg.message_thread_id != config.TOPIC_ID:
        return

    if msg.video:
        item = {"type": "video", "file_id": msg.video.file_id, "message_id": msg.message_id}
    elif msg.photo:
        item = {"type": "photo", "file_id": msg.photo[-1].file_id, "message_id": msg.message_id}
    elif msg.voice:
        item = {"type": "voice", "file_id": msg.voice.file_id, "message_id": msg.message_id}
    elif msg.video_note:
        item = {"type": "video_note", "file_id": msg.video_note.file_id, "message_id": msg.message_id}
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

    if action == "x":
        await query.message.delete()
        return

    if not entry:
        await query.answer("Данные устарели — перезапустите бота.", show_alert=True)
        return

    if action == "d":
        save_deferred(
            title=entry["title"],
            analysis=entry["quick"],
            media_path=entry["media_paths"][0] if entry["media_paths"] else None,
        )
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            message_thread_id=query.message.message_thread_id,
            text="📌 Сохранено в отложенные.",
        )

    elif action == "s":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
        try:
            image_paths = [Path(p) for p in entry.get("image_paths", []) if Path(p).exists()]
            transcripts = entry.get("transcripts", [])
            instructions = await deep_analyze(entry["quick"], image_paths, transcripts)
        except Exception as e:
            instructions = f"⚠️ Ошибка глубокого анализа: {e}"

        chunks = [instructions[i:i+4000] for i in range(0, len(instructions), 4000)]
        for chunk in chunks:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                message_thread_id=query.message.message_thread_id,
                text=f"🚀 *ИНСТРУКЦИИ:*\n\n{chunk}" if chunks.index(chunk) == 0 else chunk,
                parse_mode="Markdown",
            )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages containing supported URLs."""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    if not msg.from_user or msg.from_user.id != config.OWNER_USER_ID:
        return
    if config.TELEGRAM_CHAT_ID and msg.chat_id != config.TELEGRAM_CHAT_ID:
        return
    if config.TOPIC_ID and msg.message_thread_id != config.TOPIC_ID:
        return

    from analyzers.url_downloader import is_supported_url, download_url
    from analyzers.video import extract_frames

    url = msg.text.strip()
    if not is_supported_url(url):
        return

    status_msg = None
    try:
        status_msg = await msg.reply_text("⏳ Скачиваю и анализирую...")
    except Exception:
        pass

    try:
        result = await download_url(url)
        video_path = result["video_path"]
        transcripts = []
        if result["transcript"]:
            transcripts.append(result["transcript"])
        if result["description"]:
            transcripts.append(f"Описание: {result['description']}")

        image_paths = await extract_frames(video_path, n=6)
        video_path.unlink(missing_ok=True)

        quick = await quick_analyze(image_paths, transcripts)

        title = result["title"]
        reply = f"🔗 *{title}*\n\n📝 *Транскрипция:*\n{transcripts[0] if transcripts else '—'}\n\n🔍 *Анализ:*\n{quick}"
        if len(reply) > 4000:
            reply = reply[:3990] + "\n_...[обрезано]_"

        store_key = uuid.uuid4().hex
        context.application.bot_data.setdefault("analyses", {})[store_key] = {
            "title": title,
            "quick": quick,
            "image_paths": [str(p) for p in image_paths],
            "transcripts": transcripts,
            "media_paths": [],
        }

        if status_msg:
            await status_msg.delete()

        await context.bot.send_message(
            chat_id=msg.chat_id,
            message_thread_id=msg.message_thread_id,
            text=reply,
            parse_mode="Markdown",
            reply_markup=action_keyboard(store_key),
            reply_to_message_id=msg.message_id,
        )

    except Exception as e:
        logger.error("[URLHandler] %s", e)
        if status_msg:
            await status_msg.edit_text(f"⚠️ Ошибка: {e}")
