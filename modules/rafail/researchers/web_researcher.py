"""WebResearcher — поиск мануалов и технической документации в интернете."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    is_pdf: bool = False


class WebResearcher:
    """Ищет мануалы и техническую документацию по названию оборудования."""

    MANUFACTURER_SITES = {
        "deye": "solar.deye.com.cn",
        "pylontech": "en.pylontech.com.cn",
        "ja solar": "www.jasolar.com",
        "longi": "www.longi.com",
        "huawei": "solar.huawei.com",
        "solis": "www.solisinverters.com",
        "growatt": "www.growatt.com",
    }

    async def search_manual(self, brand: str, model: str) -> list[SearchResult]:
        """Найти мануал по бренду и модели через поисковые запросы."""
        queries = [
            f"{brand} {model} installation manual PDF",
            f"{brand} {model} інструкція монтаж PDF",
            f"{brand} {model} user manual datasheet",
        ]
        results = []
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
        ) as c:
            for query in queries[:2]:
                try:
                    r = await c.get(
                        "https://www.google.com/search", params={"q": query, "num": 5}
                    )
                    soup = BeautifulSoup(r.text, "lxml")
                    for a in soup.select("a[href]")[:10]:
                        raw_href = a.get("href", "")
                        href = str(raw_href) if raw_href else ""
                        if "/url?q=" in href:
                            url = href.split("/url?q=")[1].split("&")[0]
                            if url.startswith("http"):
                                is_pdf = url.lower().endswith(".pdf")
                                results.append(
                                    SearchResult(
                                        title=a.get_text()[:100],
                                        url=url,
                                        snippet="",
                                        is_pdf=is_pdf,
                                    )
                                )
                except Exception as e:
                    logger.warning("[researcher] поиск '%s': %s", query, e)

        # приоритет PDF
        results.sort(key=lambda r: (not r.is_pdf, r.url))
        return results[:5]

    async def find_manufacturer_page(self, brand: str, model: str) -> str | None:
        """Найти страницу продукта на сайте производителя."""
        brand_lower = brand.lower()
        site = self.MANUFACTURER_SITES.get(brand_lower)
        if not site:
            return None

        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
        ) as c:
            try:
                r = await c.get(f"https://{site}/search?q={model}")
                soup = BeautifulSoup(r.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = str(a["href"])
                    if model.lower().replace("-", "").replace(
                        " ", ""
                    ) in href.lower().replace("-", "").replace(" ", ""):
                        if href.startswith("http"):
                            return href
                        return f"https://{site}{href}"
            except Exception as e:
                logger.warning("[researcher] сайт производителя %s: %s", site, e)
        return None

    async def search_for_equipment(self, query: str) -> list[SearchResult]:
        """Общий поиск по запросу."""
        return await self.search_manual(*query.split(" ", 1)) if " " in query else []

    async def get_pdf_url(self, brand: str, model: str) -> str | None:
        """Найти прямую ссылку на PDF мануал."""
        results = await self.search_manual(brand, model)
        for r in results:
            if r.is_pdf:
                return r.url
        return None
