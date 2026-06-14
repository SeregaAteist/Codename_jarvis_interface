import logging

import httpx
from config import cfg

from agents.db_agent import get_watchlist

logger = logging.getLogger("notify")

TG_API = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"

# Статусы, по которым шлём уведомления о новых сериях (A-9)
NOTIFY_STATUSES = ("watching", "planned")


async def send_message(text: str, parse_mode: str = "HTML") -> bool:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        logger.info("(no token) %s", text)
        return False
    thread_id = getattr(cfg, "ANIME_TOPIC_ID", 0)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TG_API}/sendMessage",
                json={
                    "chat_id": cfg.GROUP_CHAT_ID or cfg.TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": False,
                    **({"message_thread_id": thread_id} if thread_id else {}),
                },
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
    """Красивое уведомление о новинках аниме с рейтингом и жанрами."""
    if not new_items:
        return

    filtered, from_watchlist = filter_by_watchlist(new_items)
    if not filtered:
        logger.info("Новинок по вотчлисту нет (%d отфильтровано).", len(new_items))
        return

    count = len(filtered)
    if from_watchlist:
        header = f"🔔 <b>Нові серії — ваш вотчліст ({count}):</b>\n\n"
    else:
        header = f"🎌 <b>Нові аніме ({count}):</b>\n\n"

    lines = [header]
    for item in filtered[:10]:
        title = (item.get("title") or "")[:50]
        genres = ", ".join((item.get("genres") or [])[:2])
        rating = item.get("mal_score") or item.get("score", "")
        ep = item.get("episode", "")
        url = item.get("url", "")

        line = f"▶️ <b><a href='{url}'>{title}</a></b>"
        if ep:
            line += f" [{ep}]"
        if rating:
            line += f" ⭐{rating}"
        if genres:
            line += f"\n   {genres}"
        lines.append(line + "\n")

    await send_message("".join(lines))


async def notify_scan_complete(total: int, new_count: int) -> None:
    msg = (
        f"✅ <b>Сканирование завершено</b>\n"
        f"Просмотрено тайтлов: {total}\n"
        f"Обновлений/новинок: {new_count}"
    )
    await send_message(msg)
