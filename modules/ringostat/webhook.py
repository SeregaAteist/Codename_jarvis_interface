"""Ringostat webhook receiver — порт 7736."""

from __future__ import annotations

import hmac
import json
import logging
import time
from collections import deque

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from modules.kommo.client import KommoClient
from modules.ringostat.employees import find_by_sip
from modules.ringostat.notifier import CallNotifier
from shared.config.settings import get_settings
from shared.models.ringostat import CallDisposition

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

        # ANSWERED → топик; MISSED/NO ANSWER/BUSY → личка
        disposition_raw = str(data.get("disposition", "")).upper()
        is_urgent = disposition_raw != CallDisposition.ANSWERED.value

        emp = find_by_sip(str(data.get("employee") or data.get("employee_ext") or ""))
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
        return {"status": "ok"}


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
