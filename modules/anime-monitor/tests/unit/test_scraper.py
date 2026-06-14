"""Scraper: парсинг HTML-фикстуры без сети (respx)."""

import httpx
import respx
from agents.scraper_agent import fetch_page
from config import cfg

_HTML = """
<html><body>
  <div class="shortstory">
    <div class="shortstoryHead"><h2>
      <a href="https://animevost.org/tip/tv/1-test.html">Тест / Test [1-12 из 12]</a>
    </h2><span>12 из 12</span></div>
    <img src="/img/1.jpg">
    <div class="ratbox"><span class="voted">9.1</span></div>
    <div class="shortstoryContent"><p>фэнтези, приключения</p></div>
  </div>
  <div class="shortstory">
    <h2><a href="https://animevost.org/tip/tv/2-x.html">Второй [5 из 24]</a></h2>
  </div>
  <div class="shortstory"><p>битая карточка без ссылки</p></div>
</body></html>
"""


async def test_fetch_page_parses_cards():
    with respx.mock:
        respx.get(f"{cfg.BASE_URL}/").mock(return_value=httpx.Response(200, text=_HTML))
        async with httpx.AsyncClient() as client:
            items = await fetch_page(client, page=1)

    assert len(items) == 2  # битая карточка пропущена
    first = items[0]
    assert first["title"].startswith("Тест / Test")
    assert first["url"].endswith("1-test.html")
    assert first["img_url"] == f"{cfg.BASE_URL}/img/1.jpg"  # относительный → абсолютный
    assert first["episode"] == "12 из 12"
    assert first["rating"] == "9.1"
    assert "фэнтези" in first["genres"]


async def test_fetch_page_error_returns_empty():
    with respx.mock:
        respx.get(f"{cfg.BASE_URL}/").mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            assert await fetch_page(client, page=1) == []


_CAT_HTML = """
<html><body>
  <div class="shortstory">
    <h2><a href="https://animevost.org/tip/tv/3-new.html">Новый [1 из 12]</a></h2>
    <div class="shortstoryContent">Год выхода: 2025 Жанр: фэнтези, экшен Тип: ТВ</div>
  </div>
  <div class="shortstory">
    <h2><a href="https://animevost.org/tip/tv/4-old.html">Старый [12 из 12]</a></h2>
    <div class="shortstoryContent">Год выхода: 2010 Жанр: меха Тип: ТВ</div>
  </div>
</body></html>
"""


async def test_category_year_filter():
    from agents.scraper_agent import fetch_category_page

    with respx.mock:
        respx.get(f"{cfg.BASE_URL}/zhanr/fentezi/").mock(
            return_value=httpx.Response(200, text=_CAT_HTML)
        )
        async with httpx.AsyncClient() as client:
            items, all_below = await fetch_category_page(
                client, "/zhanr/fentezi/", 1, 2020, 2026
            )

    assert len(items) == 1 and items[0]["year"] == "2025"
    assert "фэнтези" in items[0]["genres"]
    assert all_below is False  # на странице есть 2025


async def test_scrape_all_pages_dedup(monkeypatch):
    import agents.scraper_agent as mod

    monkeypatch.setattr(cfg, "PAGES_TO_SCAN", 2)
    monkeypatch.setattr(cfg, "REQUEST_DELAY", 0)

    dup = {"title": "Дубль", "url": "https://x/same"}

    async def fake_fetch(client, page):
        return [dup]

    monkeypatch.setattr(mod, "fetch_page", fake_fetch)

    items = await mod.scrape_all_pages()
    assert len(items) == 1  # дедуп по url между страницами
