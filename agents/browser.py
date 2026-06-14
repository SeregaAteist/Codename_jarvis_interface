"""Browser agent — web search, page fetch, price lookup via DuckDuckGo."""

from __future__ import annotations

import re
import subprocess
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

try:
    from core.cache import search_cache as _search_cache
except ImportError:
    _search_cache = None

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def search_web(query: str, max_results: int = 3) -> list[dict]:
    """DuckDuckGo Lite search — no API key required."""
    try:
        url = f"https://lite.duckduckgo.com/lite/?q={quote(query)}"
        resp = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")
        results = []
        i = 0
        while i < len(rows) and len(results) < max_results:
            row = rows[i]
            a = row.find("a")
            if a and row.find("td", attrs={"valign": "top"}):
                title = a.get_text(strip=True)
                snippet = ""
                url_txt = ""
                # Next non-empty rows: snippet row, then URL row
                for j in range(i + 1, min(i + 4, len(rows))):
                    td_snip = rows[j].find("td", class_="result-snippet")
                    td_link = rows[j].find("span", class_="link-text")
                    if td_snip and not snippet:
                        snippet = td_snip.get_text(strip=True)
                    if td_link and not url_txt:
                        url_txt = td_link.get_text(strip=True)
                if title and snippet:
                    results.append({"title": title, "snippet": snippet, "url": url_txt})
            i += 1
        return results
    except Exception as e:
        return [{"title": "Ошибка поиска", "snippet": str(e), "url": ""}]


def fetch_page(url: str, max_chars: int = 3000) -> str:
    """Fetch and clean text content from a URL."""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        resp = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        return text[:max_chars]
    except Exception as e:
        return f"Ошибка загрузки: {e}"


def get_price(product: str) -> str:
    """Search for product price via DuckDuckGo snippets."""
    results = search_web(f"цена {product} купить 2025", max_results=3)
    if not results:
        return "Цена не найдена."
    snippets = [r["snippet"] for r in results if r["snippet"]]
    return "\n".join(snippets[:3])


def get_weather_detailed(city: str = "Одесса") -> dict:
    """Current weather from wttr.in (no API key)."""
    try:
        resp = httpx.get(
            f"https://wttr.in/{quote(city)}?format=j1",
            timeout=5,
        )
        data = resp.json()
        current = data["current_condition"][0]
        return {
            "temp": current["temp_C"],
            "feels": current["FeelsLikeC"],
            "desc": current["weatherDesc"][0]["value"],
            "humidity": current["humidity"],
            "wind": current["windspeedKmph"],
        }
    except Exception as e:
        return {"error": str(e)}


def smart_search(query: str) -> str:
    """Search and return formatted raw results (cached 30 min)."""
    cache_key = f"search_{query.lower().strip()}"
    if _search_cache:
        cached = _search_cache.get(cache_key)
        if cached:
            return cached

    results = search_web(query, max_results=3)
    if not results:
        return "Ничего не найдено по запросу."
    lines = [f"По запросу «{query}» нашёл:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n{r['snippet']}\n")
    result = "\n".join(lines).strip()

    if _search_cache:
        _search_cache.set(cache_key, result)
    return result


def open_url_in_browser(url: str) -> str:
    """Open URL in the default macOS browser."""
    if not url.startswith("http"):
        url = "https://" + url
    subprocess.run(["open", url], check=False)
    return f"Открываю {url}, сэр."


from agents.registry import register  # noqa: E402


@register
class BrowserAgent:
    name = "browser"
    icon = "🌐"

    def is_available(self) -> bool:
        try:
            httpx.get("https://duckduckgo.com", timeout=3)
            return True
        except Exception:
            return False

    def search(self, query: str) -> str:
        return smart_search(query)

    def price(self, product: str) -> str:
        return get_price(product)

    def fetch(self, url: str) -> str:
        return fetch_page(url)

    def open(self, url: str) -> str:
        return open_url_in_browser(url)


if __name__ == "__main__":
    print("=== Тест поиска ===")
    for r in search_web("курс доллара сегодня")[:2]:
        print(f"  {r['title']}: {r['snippet'][:80]}")

    print("\n=== Тест страницы ===")
    print(fetch_page("https://wttr.in/Odessa?format=3")[:200])
