from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.rafail.researchers.web_researcher import SearchResult, WebResearcher


@pytest.fixture
def researcher():
    return WebResearcher()


def test_manufacturer_sites_has_deye(researcher):
    assert "deye" in researcher.MANUFACTURER_SITES


@pytest.mark.asyncio
async def test_search_manual_returns_list(researcher):
    with patch("httpx.AsyncClient") as mock:
        mock.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=MagicMock(
                text="<html><body></body></html>", raise_for_status=lambda: None
            )
        )
        results = await researcher.search_manual("Deye", "SUN-10K")
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_get_pdf_url_returns_none_when_no_pdf(researcher):
    researcher.search_manual = AsyncMock(
        return_value=[
            SearchResult(
                title="test", url="http://example.com/page", snippet="", is_pdf=False
            )
        ]
    )
    result = await researcher.get_pdf_url("Deye", "SUN-10K")
    assert result is None


@pytest.mark.asyncio
async def test_get_pdf_url_returns_pdf(researcher):
    researcher.search_manual = AsyncMock(
        return_value=[
            SearchResult(
                title="manual",
                url="http://example.com/manual.pdf",
                snippet="",
                is_pdf=True,
            )
        ]
    )
    result = await researcher.get_pdf_url("Deye", "SUN-10K")
    assert result == "http://example.com/manual.pdf"


@pytest.mark.asyncio
async def test_find_manufacturer_page_unknown_brand(researcher):
    result = await researcher.find_manufacturer_page("UnknownBrand", "X100")
    assert result is None


@pytest.mark.asyncio
async def test_find_manufacturer_page_known_brand_with_link():
    html = '<html><body><a href="/products/sun-10k">SUN-10K page</a></body></html>'
    resp = MagicMock(text=html)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)

    r = WebResearcher()
    with patch("httpx.AsyncClient", return_value=client):
        result = await r.find_manufacturer_page("deye", "sun-10k")
    assert result == "https://solar.deye.com.cn/products/sun-10k"


@pytest.mark.asyncio
async def test_find_manufacturer_page_known_brand_no_match():
    html = "<html><body><a href='/other'>other</a></body></html>"
    resp = MagicMock(text=html)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)

    r = WebResearcher()
    with patch("httpx.AsyncClient", return_value=client):
        result = await r.find_manufacturer_page("deye", "SUN-10K")
    assert result is None


@pytest.mark.asyncio
async def test_find_manufacturer_page_http_error():
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(side_effect=Exception("timeout"))

    r = WebResearcher()
    with patch("httpx.AsyncClient", return_value=client):
        result = await r.find_manufacturer_page("deye", "SUN-10K")
    assert result is None


@pytest.mark.asyncio
async def test_search_for_equipment_with_space(researcher):
    researcher.search_manual = AsyncMock(return_value=[])
    result = await researcher.search_for_equipment("Deye SUN-10K")
    assert result == []
    researcher.search_manual.assert_called_once_with("Deye", "SUN-10K")


@pytest.mark.asyncio
async def test_search_for_equipment_no_space(researcher):
    researcher.search_manual = AsyncMock(return_value=[])
    result = await researcher.search_for_equipment("Deye")
    assert result == []
    researcher.search_manual.assert_not_called()


@pytest.mark.asyncio
async def test_search_manual_sorts_pdfs_first(researcher):
    html = """<html><body>
    <a href="/url?q=http://example.com/doc.html&other">HTML</a>
    <a href="/url?q=http://example.com/manual.pdf&other">PDF</a>
    </body></html>"""
    resp = MagicMock(text=html)
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)

    with patch("httpx.AsyncClient", return_value=client):
        results = await researcher.search_manual("Deye", "SUN-10K")

    pdf_results = [r for r in results if r.is_pdf]
    if pdf_results:
        assert results[0].is_pdf
