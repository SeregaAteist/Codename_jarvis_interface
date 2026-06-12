import asyncio
import logging
import re
import httpx
from bs4 import BeautifulSoup
from config import cfg

logger = logging.getLogger("scraper")


HEADERS = {
    "User-Agent": cfg.USER_AGENT,
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": cfg.BASE_URL,
}


async def fetch_page(client: httpx.AsyncClient, page: int) -> list[dict]:
    url = f"{cfg.BASE_URL}/page/{page}/" if page > 1 else f"{cfg.BASE_URL}/"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Ошибка страницы {page}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = []

    for card in soup.select("div.shortstory, div.short, article.shortstory"):
        try:
            title_el = (
                card.select_one("div.shortstoryHead h2 a") or
                card.select_one("h2 a") or
                card.select_one(".title a")
            )
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url_link = title_el.get("href", "")

            img_el = card.select_one("img")
            img_url = img_el.get("src", "") if img_el else ""
            if img_url and img_url.startswith("/"):
                img_url = cfg.BASE_URL + img_url

            episode_el = card.select_one(".shortstoryHead span, .epizode, .series")
            episode = episode_el.get_text(strip=True) if episode_el else ""

            rating_el = card.select_one(".ratbox .voted, .rating")
            rating = rating_el.get_text(strip=True) if rating_el else ""

            genres_el = card.select_one(".shortstoryContent p, .genres")
            genres = genres_el.get_text(strip=True)[:100] if genres_el else ""

            items.append({
                "title": title,
                "url": url_link,
                "img_url": img_url,
                "episode": episode,
                "rating": rating,
                "genres": genres,
            })
        except Exception as e:
            logger.warning(f"Ошибка карточки: {e}")
            continue

    logger.info(f"Страница {page}: найдено {len(items)} тайтлов")
    return items


async def fetch_category_page(
    client: httpx.AsyncClient,
    base_path: str,
    page: int,
    year_min: int,
    year_max: int,
) -> tuple[list[dict], bool]:
    """Returns (items_in_range, all_years_below_min)."""
    url = f"{cfg.BASE_URL}{base_path}" if page == 1 else f"{cfg.BASE_URL}{base_path}page/{page}/"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Ошибка страницы {page}: {e}")
        return [], False

    soup = BeautifulSoup(resp.text, "lxml")
    items = []
    page_years = []

    for card in soup.select("div.shortstory, div.short, article.shortstory"):
        try:
            title_el = (
                card.select_one("div.shortstoryHead h2 a") or
                card.select_one("h2 a") or
                card.select_one(".title a")
            )
            if not title_el:
                continue

            title    = title_el.get_text(strip=True)
            url_link = title_el.get("href", "")

            img_el  = card.select_one("img")
            img_url = img_el.get("src", "") if img_el else ""
            if img_url and img_url.startswith("/"):
                img_url = cfg.BASE_URL + img_url

            episode_el = card.select_one(".shortstoryHead span, .epizode, .series")
            episode    = episode_el.get_text(strip=True) if episode_el else ""

            rating_el = card.select_one(".ratbox .voted, .rating")
            rating    = rating_el.get_text(strip=True) if rating_el else ""

            content_el = card.select_one("div.shortstoryContent")
            content    = content_el.get_text(" ", strip=True) if content_el else ""

            year_match = re.search(r"Год выхода[:\s]*(\d{4})", content)
            year = int(year_match.group(1)) if year_match else 0
            if year:
                page_years.append(year)

            genres_match = re.search(r"Жанр[:\s]*([^Т]+?)(?:Тип|$)", content)
            genres = genres_match.group(1).strip()[:100] if genres_match else ""

            if year_min <= year <= year_max:
                items.append({
                    "title":   title,
                    "url":     url_link,
                    "img_url": img_url,
                    "episode": episode,
                    "rating":  rating,
                    "genres":  genres,
                    "year":    str(year) if year else "",
                })
        except Exception as e:
            logger.warning(f"Ошибка карточки: {e}")
            continue

    all_below = bool(page_years) and all(y < year_min for y in page_years)
    logger.info(f"Страница {page}: найдено {len(items)} в диапазоне "
          f"(годы на странице: {sorted(set(page_years), reverse=True)})")
    return items, all_below


async def scrape_category(
    base_path: str,
    year_min: int = 2020,
    year_max: int = 2026,
    max_pages: int = 200,
) -> list[dict]:
    """Scrape a genre/category page with year filtering and early stop."""
    all_items: list[dict] = []
    below_count = 0  # consecutive pages where all years < year_min

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            items, all_below = await fetch_category_page(
                client, base_path, page, year_min, year_max
            )
            all_items.extend(items)

            if all_below:
                below_count += 1
                if below_count >= 3:
                    logger.info(f"3 страницы подряд ниже {year_min} — останавливаемся.")
                    break
            else:
                below_count = 0

            if page < max_pages:
                await asyncio.sleep(cfg.REQUEST_DELAY)

    seen_urls: set[str] = set()
    unique = []
    for item in all_items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique.append(item)

    logger.info(f"Итого уникальных ({year_min}–{year_max}): {len(unique)}")
    return unique


async def scrape_all_pages() -> list[dict]:
    all_items = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page in range(1, cfg.PAGES_TO_SCAN + 1):
            items = await fetch_page(client, page)
            all_items.extend(items)
            if page < cfg.PAGES_TO_SCAN:
                await asyncio.sleep(cfg.REQUEST_DELAY)

    seen_urls = set()
    unique = []
    for item in all_items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique.append(item)

    logger.info(f"Итого уникальных: {len(unique)}")
    return unique
