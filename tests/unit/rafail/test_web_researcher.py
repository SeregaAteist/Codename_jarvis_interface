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
