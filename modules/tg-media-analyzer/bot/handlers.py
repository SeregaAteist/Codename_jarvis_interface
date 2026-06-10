from __future__ import annotations
import asyncio
import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

import config
from analyzers.batcher import smart_batch
from analyzers.gemini_video import analyze_video_native
from bot.keyboards import action_keyboard
from db.storage import init_db, save_deferred
from pipeline.quick import quick_analyze, _gemini_pool, QUICK_PROMPT
from pipeline.deep import deep_analyze

logger = logging.getLogger(__name__)

_batches: dict[tuple, list[dict]] = {}
_batch_tasks: dict[tuple, asyncio.Task] = {}


def _owner_ok(msg) -> bool:
    if not msg.from_user or msg.from_user.id != config.OWNER_USER_ID:
        return False
    if config.TELEGRAM_CHAT_ID and msg.chat_id != config.TELEGRAM_CHAT_ID:
        return False
    return True


async def _process_batch(key: tuple, items: list[dict], app) -> None:
    chat_id, thread_id = key
    batches = smart_batch(items)

    for batch in batches:
        status_msg = None
        try:
            status_msg = await app.bot.send_message(
                chat_id=chat_id, message_thread_id=thread_id,
                text=f"⏳ Анализирую {len(batch.items)} файл(ов)...",
            )
        except Exception:
            pass

        image_paths: list[Path] = []
        video_paths: list[Path] = []
        media_paths: list[str] = []
        reply_to: int | None = None

        for item in batch.items:
            try:
                tg_file = await app.bot.get_file(item["file_id"])
                suffix = {"video": ".mp4", "voice": ".ogg", "photo": ".jpg",
                          "video_note": ".mp4"}.get(item["type"], ".bin")
                local = config.TMP_DIR / f"{uuid.uuid4().hex}{suffix}"
                await tg_file.download_to_drive(local)
                media_paths.append(str(local))
                if item["type"] == "photo":
                    image_paths.append(local)
                else:
                    video_paths.append(local)
                if "message_id" in item and reply_to is None:
                    reply_to = item["message_id"]
            except Exception as e:
                logger.error("Media error: %s", e)

        # Анализ: видео — нативно через Gemini (звук+видео), фото — батчем
        analyses = []
        for vid in video_paths:
            res = await analyze_video_native(vid, QUICK_PROMPT, _gemini_pool)
            analyses.append(res)
        if image_paths:
            res = await quick_analyze(image_paths, [])
            analyses.append(res)

        quick = "\n\n---\n\n".join(analyses) if analyses else "⚠️ Нет контента"

        reply = f"🔍 *Анализ:*\n{quick}"
        if len(reply) > 4000:
            reply = reply[:3990] + "\n_...[обрезано]_"

        store_key = uuid.uuid4().hex
        app.bot_data.setdefault("analyses", {})[store_key] = {
            "title": f"Медиа — {len(batch.items)} файл(ов)",
            "quick": quick,
            "image_paths": [str(p) for p in image_paths],
            "video_paths": [str(p) for p in video_paths],
            "transcripts": [],
            "media_paths": media_paths,
        }

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        await app.bot.send_message(
            chat_id=chat_id, message_thread_id=thread_id,
            text=reply, parse_mode="Markdown",
            reply_markup=action_keyboard(store_key),
            reply_to_message_id=reply_to,
        )

        for p in media_paths:
            Path(p).unlink(missing_ok=True)

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
        logger.error("Timer error: %s", e, exc_info=True)
        _batches.pop(key, None)
        _batch_tasks.pop(key, None)


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not _owner_ok(msg):
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
    try:
        await context.bot.set_message_reaction(chat_id=msg.chat_id, message_id=msg.message_id, reaction="👀")
    except Exception:
        pass


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text or not _owner_ok(msg):
        return
    if config.TOPIC_ID and msg.message_thread_id != config.TOPIC_ID:
        return

    from analyzers.url_downloader import is_supported_url, download_url
    url = msg.text.strip()
    if not is_supported_url(url):
        return

    status = None
    try:
        status = await msg.reply_text("⏳ Скачиваю и анализирую...")
    except Exception:
        pass

    try:
        result = await download_url(url)
        video_path = result["video_path"]
        res = await analyze_video_native(video_path, QUICK_PROMPT, _gemini_pool)
        video_path.unlink(missing_ok=True)

        title = result["title"]
        reply = f"🔗 *{title}*\n\n🔍 *Анализ:*\n{res}"
        if len(reply) > 4000:
            reply = reply[:3990] + "\n_...[обрезано]_"

        store_key = uuid.uuid4().hex
        context.application.bot_data.setdefault("analyses", {})[store_key] = {
            "title": title, "quick": res,
            "image_paths": [], "video_paths": [], "transcripts": [],
            "media_paths": [],
        }

        if status:
            await status.delete()
        await context.bot.send_message(
            chat_id=msg.chat_id, message_thread_id=msg.message_thread_id,
            text=reply, parse_mode="Markdown",
            reply_markup=action_keyboard(store_key),
            reply_to_message_id=msg.message_id,
        )
    except Exception as e:
        logger.error("[URL] %s", e)
        if status:
            await status.edit_text(f"⚠️ Ошибка: {e}")


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
        await query.answer("Данные устарели.", show_alert=True)
        return

    if action == "d":
        save_deferred(title=entry["title"], analysis=entry["quick"],
                      media_path=None)
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
            imgs = [Path(p) for p in entry.get("image_paths", []) if Path(p).exists()]
            instructions = await deep_analyze(entry["quick"], imgs, entry.get("transcripts", []))
        except Exception as e:
            instructions = f"⚠️ Ошибка: {e}"
        chunks = [instructions[i:i+4000] for i in range(0, len(instructions), 4000)]
        for i, chunk in enumerate(chunks):
            text = f"🚀 *ИНСТРУКЦИИ:*\n\n{chunk}" if i == 0 else chunk
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                message_thread_id=query.message.message_thread_id,
                text=text, parse_mode="Markdown",
            )
