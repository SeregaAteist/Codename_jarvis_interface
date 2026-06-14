"""Ringostat webhook receiver — порт 7736."""

from __future__ import annotations

import hmac
import json
import logging
import time
from collections import deque

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from modules.kommo.client import KommoClient
from modules.ringostat.employees import find_by_sip
from modules.ringostat.notifier import CallNotifier
from shared.config.settings import get_settings
from shared.models.ringostat import CallDisposition, CallEvent

load_dotenv(override=False)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# rate limit: не больше 60 хитов/мин (эндпоинт публичный через Tailscale Funnel)
_RATE_LIMIT, _RATE_WINDOW = 60, 60.0
_hits: deque[float] = deque()


def _rate_ok() -> bool:
    now = time.monotonic()
    while _hits and now - _hits[0] > _RATE_WINDOW:
        _hits.popleft()
    if len(_hits) >= _RATE_LIMIT:
        return False
    _hits.append(now)
    return True


class RingostatWebhookHandler:
    """Обрабатывает входящие вебхуки Ringostat."""

    def __init__(self, kommo: KommoClient, notifier: CallNotifier) -> None:
        self._kommo = kommo
        self._notifier = notifier
        self._secret = get_settings().ringostat_webhook_secret

    def verify_token(self, token: str | None) -> bool:
        if not token or not self._secret:
            return False
        return hmac.compare_digest(token, self._secret)

    async def handle(self, data: dict[str, object]) -> dict[str, str]:
        phone = str(data.get("caller_id") or data.get("called_id") or "")
        if not phone:
            return {"status": "skip", "reason": "no phone"}

        disposition_raw = str(data.get("disposition", "")).upper()
        is_urgent = disposition_raw != CallDisposition.ANSWERED.value

        try:
            disposition_enum = CallDisposition(disposition_raw)
        except ValueError:
            disposition_enum = CallDisposition.NO_ANSWER

        event = CallEvent(
            call_id=str(data.get("call_id", "")),
            caller_id=phone,
            called_id=str(data.get("called_id", "")),
            duration=int(data.get("duration", 0) or 0),
            disposition=disposition_enum,
            audio_url=str(data.get("record_url") or data.get("audio_url") or "")
            or None,
            manager_sip=str(data.get("sip") or data.get("manager_sip") or "") or None,
        )

        emp = find_by_sip(event.manager_sip or "")
        manager_name = emp["name"] if emp else ""

        logger.info(
            "[Ringostat] RAW:\n%s", json.dumps(data, ensure_ascii=False, indent=2)
        )

        contact = await self._kommo.find_contact_by_phone(phone)
        if not contact:
            await self._notifier.notify_unknown(phone)
            return {"status": "unknown_contact"}

        leads = await self._kommo.get_contact_leads(contact.id)
        lead = leads[-1] if leads else None
        lead_url = self._kommo.get_lead_url(lead.id) if lead else ""
        lead_name = lead.name if lead else "Сделка не найдена"

        await self._notifier.notify_call(
            phone=phone,
            contact_name=contact.name,
            lead_name=lead_name,
            lead_url=lead_url,
            manager_name=manager_name,
            is_urgent=is_urgent,
        )

        if (
            event.audio_url
            and event.disposition == CallDisposition.ANSWERED
            and event.duration > 30
        ):
            import asyncio

            asyncio.create_task(
                self._process_call_audio(event, contact.name, lead_name, lead_url, lead)
            )

        return {"status": "ok"}

    async def _process_call_audio(
        self,
        event: CallEvent,
        contact_name: str,
        lead_name: str,
        lead_url: str,
        lead: object,
    ) -> None:
        """Асинхронная обработка аудио после ответа на webhook."""
        try:
            from modules.ringostat.analyzer import get_analyzer, get_transcriber
            from modules.ringostat.audio import get_downloader

            downloader = get_downloader()
            audio_path = await downloader.download(event.call_id, event.audio_url or "")
            if not audio_path:
                return

            transcript = await get_transcriber().transcribe(
                audio_path,
                {
                    "call_id": event.call_id,
                    "caller_id": event.caller_id,
                    "duration": event.duration,
                },
            )

            result = await get_analyzer().analyze(
                transcript,
                {
                    "call_id": event.call_id,
                    "caller_id": event.caller_id,
                    "duration": event.duration,
                    "manager_name": "",
                },
            )

            cfg = get_settings()
            text = (
                f"📞 <b>Аналіз дзвінка</b>\n"
                f"👤 {contact_name} | {event.caller_id}\n"
                f"🔗 <a href='{lead_url}'>{lead_name}</a>\n"
                f"⏱ {event.duration} сек\n\n"
                f"📋 <b>Резюме:</b> {result.summary}\n"
                f"📊 <b>Ефективність:</b> {result.script_effectiveness}\n"
            )
            if result.agreements:
                text += (
                    "✅ <b>Домовленості:</b>\n"
                    + "\n".join(f"• {a}" for a in result.agreements)
                    + "\n"
                )
            if result.objections:
                text += (
                    "⚠️ <b>Заперечення:</b>\n"
                    + "\n".join(f"• {o}" for o in result.objections)
                    + "\n"
                )
            if result.next_step:
                text += f"➡️ <b>Наступний крок:</b> {result.next_step}\n"

            work_token = cfg.jarvis_work_bot_token or cfg.telegram_bot_token
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(
                    f"https://api.telegram.org/bot{work_token}/sendMessage",
                    json={
                        "chat_id": cfg.work_chat_id,
                        "message_thread_id": cfg.work_topic_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )

            if lead is not None:
                await self._kommo.add_note(
                    lead.id,
                    f"Транскрипт дзвінка {event.call_id}:\n\n{transcript[:3000]}",
                )

            downloader.cleanup(event.call_id)

            if result.objections:
                await self._update_script_registry(result, event)

            if result.objections and result.script_effectiveness in ("low", "medium"):
                await self._signal_rafail(result)

        except Exception as e:
            logger.error("[webhook] ошибка обработки аудио %s: %s", event.call_id, e)

    async def _update_script_registry(self, result: object, event: object) -> None:
        """Оновити реєстр скриптів на основі результату дзвінка."""
        try:
            from modules.rafail.core.profile_manager import get_profile_manager
            from modules.rafail.researchers.script_analyzer import ScriptAnalyzer

            profile = get_profile_manager().active
            scripts_dir = profile.equipment_dir.parent / "scripts"
            analyzer = ScriptAnalyzer(scripts_dir)

            updated = await analyzer.process_call_result(
                objections=result.objections,
                disposition=result.disposition,
                script_effectiveness=result.script_effectiveness,
                improvement_suggestions=result.improvement_suggestions,
                source=f"дзвінок {result.call_id} | {event.caller_id}",
            )
            if updated:
                logger.info("[webhook] оновлено скрипти: %s", updated)
        except Exception as e:
            logger.error("[webhook] _update_script_registry: %s", e)

    async def _signal_rafail(self, result: object) -> None:
        """Записать задачу для Рафаила — обновить скрипты по возражениям."""
        import os
        from pathlib import Path

        tasks_dir = Path(os.path.expanduser("~/Projects/jarvis/tasks/pending"))
        tasks_dir.mkdir(parents=True, exist_ok=True)

        objections_text = "\n".join(f"- {o}" for o in result.objections)
        suggestions_text = "\n".join(f"- {s}" for s in result.improvement_suggestions)

        task_content = (
            f"# TASK_call_signal_{result.call_id}\n"
            f"## Источник: Ringostat звонок\n"
            f"## REPLY_CHAT_ID: -1003891647143\n"
            f"## REPLY_TOPIC_ID: 205\n\n"
            f"## ЗАДАЧА\n"
            f"Рафаил, проанализируй возражения из звонка и предложи улучшение скриптов.\n\n"
            f"Возражения клиента:\n{objections_text}\n\n"
            f"Эффективность скрипта: {result.script_effectiveness}\n"
            f"Предложения по улучшению:\n{suggestions_text}\n\n"
            f"Проверь существующие скрипты в БЗ и предложи конкретные правки.\n"
        )
        task_file = tasks_dir / f"TASK_call_signal_{result.call_id}.md"
        task_file.write_text(task_content)
        logger.info("[webhook] сигнал Рафаилу создан: %s", task_file)


def create_app() -> FastAPI:
    kommo = KommoClient()
    notifier = CallNotifier()
    handler = RingostatWebhookHandler(kommo=kommo, notifier=notifier)
    app = FastAPI()

    @app.post("/webhook/ringostat")
    async def webhook(request: Request) -> JSONResponse:
        if not _rate_ok():
            raise HTTPException(status_code=429, detail="Too Many Requests")
        token = (
            request.headers.get("X-Webhook-Secret")
            or request.query_params.get("secret")
            or ""
        )
        if not handler.verify_token(token):
            raise HTTPException(status_code=403, detail="Forbidden")
        data = await request.json()
        try:
            result = await handler.handle(data)
        except Exception as e:
            logger.error("[webhook] ошибка: %s", e)
            result = {"status": "error"}
        return JSONResponse(result)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
