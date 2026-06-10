import httpx
from agents.db_agent import (
    get_watchlist, get_unnotified_episodes, mark_notified
)
from config import cfg


TG_API = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"


async def send_message(text: str, parse_mode: str = "HTML") -> bool:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        print(f"[Telegram] {text}")
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
        print(f"[Telegram] Ошибка отправки: {e}")
        return False


async def notify_new_episodes(new_items: list[dict]) -> None:
    if not new_items:
        return

    watchlist = get_watchlist()
    watching_titles = {w["title"].lower() for w in watchlist}

    priority = []
    other = []
    for item in new_items:
        if item["title"].lower() in watching_titles:
            priority.append(item)
        else:
            other.append(item)

    if priority:
        lines = ["🔔 <b>Новые серии — ваш вотчлист:</b>\n"]
        for item in priority:
            ep = f" [{item['episode']}]" if item.get("episode") else ""
            lines.append(
                f"⭐ <a href='{item['url']}'>{item['title']}</a>{ep}"
            )
        await send_message("\n".join(lines))

    if other:
        lines = [f"\n📺 <b>Новинки на сайте ({len(other)}):</b>\n"]
        for item in other[:10]:
            ep = f" [{item['episode']}]" if item.get("episode") else ""
            score = (
                f" · MAL {item['mal_score']}"
                if item.get("mal_score") else ""
            )
            lines.append(
                f"• <a href='{item['url']}'>{item['title']}</a>{ep}{score}"
            )
        await send_message("\n".join(lines))


async def notify_scan_complete(total: int, new_count: int) -> None:
    msg = (
        f"✅ <b>Сканирование завершено</b>\n"
        f"Просмотрено тайтлов: {total}\n"
        f"Обновлений/новинок: {new_count}"
    )
    await send_message(msg)
