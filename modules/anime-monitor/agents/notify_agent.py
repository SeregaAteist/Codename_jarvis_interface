import logging

import httpx

from agents.db_agent import get_watchlist
from config import cfg

logger = logging.getLogger("notify")

TG_API = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"

# Статусы, по которым шлём уведомления о новых сериях (A-9)
NOTIFY_STATUSES = ("watching", "planned")


async def send_message(text: str, parse_mode: str = "HTML") -> bool:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        logger.info("(no token) %s", text)
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TG_API}/sendMessage",
                json={
                    "chat_id": cfg.GROUP_CHAT_ID or cfg.TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": False,
                    **({"message_thread_id": cfg.THREAD_ID} if cfg.THREAD_ID else {}),
                }
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error("Ошибка отправки: %s", e)
        return False


def filter_by_watchlist(new_items: list[dict]) -> tuple[list[dict], bool]:
    """A-9: при непустом вотчлисте — только релевантные тайтлы.

    Пустой вотчлист → слать всё (прежнее поведение).
    Возвращает (items, фильтровалось_ли_по_вотчлисту).
    """
    watchlist = [w for w in get_watchlist() if w["status"] in NOTIFY_STATUSES]
    if not watchlist:
        return new_items, False
    watching_titles = {w["title"].lower() for w in watchlist}
    return [i for i in new_items if i["title"].lower() in watching_titles], True


async def notify_new_episodes(new_items: list[dict]) -> None:
    if not new_items:
        return

    filtered, from_watchlist = filter_by_watchlist(new_items)
    if not filtered:
        logger.info("Новинок по вотчлисту нет (%d отфильтровано).", len(new_items))
        return

    header = (
        "🔔 <b>Новые серии — ваш вотчлист:</b>\n"
        if from_watchlist else
        f"📺 <b>Новинки на сайте ({len(filtered)}):</b>\n"
    )
    lines = [header]
    for item in filtered[:15]:
        ep = f" [{item['episode']}]" if item.get("episode") else ""
        score = f" · MAL {item['mal_score']}" if item.get("mal_score") else ""
        lines.append(f"⭐ <a href='{item['url']}'>{item['title']}</a>{ep}{score}")
    await send_message("\n".join(lines))


async def notify_scan_complete(total: int, new_count: int) -> None:
    msg = (
        f"✅ <b>Сканирование завершено</b>\n"
        f"Просмотрено тайтлов: {total}\n"
        f"Обновлений/новинок: {new_count}"
    )
    await send_message(msg)
