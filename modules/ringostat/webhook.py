"""Ringostat webhook receiver — порт 7736."""
from __future__ import annotations
import json, logging, os, secrets, time
from collections import deque
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
app = FastAPI()

# fail-closed: без RINGOSTAT_WEBHOOK_SECRET в .env все запросы отклоняются
WEBHOOK_SECRET = os.getenv("RINGOSTAT_WEBHOOK_SECRET", "")
KOMMO_DOMAIN = os.getenv("KOMMO_DOMAIN", "lkenergy.kommo.com")

# rate limit: эндпоинт публичный (Tailscale Funnel) — не больше 60 хитов/мин
RATE_LIMIT, RATE_WINDOW = 60, 60.0
_hits: deque[float] = deque()


def _rate_ok() -> bool:
    now = time.monotonic()
    while _hits and now - _hits[0] > RATE_WINDOW:
        _hits.popleft()
    if len(_hits) >= RATE_LIMIT:
        return False
    _hits.append(now)
    return True


@app.post("/webhook/ringostat")
async def ringostat_webhook(request: Request):
    if not _rate_ok():
        raise HTTPException(status_code=429, detail="Too Many Requests")
    token = request.headers.get("X-Webhook-Secret") or request.query_params.get("secret") or ""
    if not WEBHOOK_SECRET or not secrets.compare_digest(token, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()
    logger.info("[Ringostat] RAW:\n%s", json.dumps(data, ensure_ascii=False, indent=2))

    phone = data.get("caller_id") or data.get("called_id") or ""
    if not phone:
        return JSONResponse({"status": "skip", "reason": "no phone"})

    # менеджер по SIP из ringostat.yaml (поле employee/employee_ext в payload)
    from modules.ringostat.employees import find_by_sip
    emp = find_by_sip(data.get("employee") or data.get("employee_ext") or "")
    manager_name = emp["name"] if emp else ""

    # ищем контакт и сделку в Kommo
    try:
        from modules.kommo.client import find_contact_by_phone, find_lead_by_contact, get_lead_link
        from modules.ringostat.notifier import notify_call

        contact = await find_contact_by_phone(phone)
        if contact:
            lead = await find_lead_by_contact(contact["id"])
            if lead:
                lead_url = await get_lead_link(lead)
                await notify_call(
                    phone=phone,
                    contact_name=contact.get("name", phone),
                    lead_name=lead.get("name", "Сделка"),
                    lead_url=lead_url,
                    manager_name=manager_name,
                )
            else:
                await notify_call(phone=phone, contact_name=contact.get("name", phone),
                    lead_name="Сделка не найдена",
                    lead_url=f"https://{KOMMO_DOMAIN}/contacts/detail/{contact['id']}",
                    manager_name=manager_name)
        else:
            await notify_call(phone=phone, contact_name=phone,
                lead_name="Контакт не найден в Kommo",
                lead_url=f"https://{KOMMO_DOMAIN}/leads/",
                manager_name=manager_name)
    except Exception as e:
        logger.error("[webhook] ошибка: %s", e)

    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health():
    return {"status": "ok"}
