"""Unit-тесты для RafailCollector."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.rafail.collector import RafailCollector


@pytest.fixture
def collector() -> RafailCollector:
    return RafailCollector()


def test_collector_singleton() -> None:
    from modules.rafail import collector as c

    c1 = c._get_collector()
    c2 = c._get_collector()
    assert c1 is c2


@pytest.mark.asyncio
async def test_collect_rss_empty(collector: RafailCollector) -> None:
    collector._rss = MagicMock()
    collector._rss.fetch = AsyncMock(return_value=[])

    with patch("modules.rafail.collector.kb") as mock_kb:
        result = await collector.collect_rss(
            {
                "url": "http://test.com/rss",
                "name": "Test",
                "domain": "ses",
                "track": "all",
            }
        )

    assert result == 0
    mock_kb.add_material.assert_not_called()


@pytest.mark.asyncio
async def test_collect_rss_new_items(collector: RafailCollector) -> None:
    collector._rss = MagicMock()
    collector._rss.fetch = AsyncMock(
        return_value=[
            {"url": "http://test.com/1", "title": "Заголовок 1", "body": "Тело 1"},
            {"url": "http://test.com/2", "title": "Заголовок 2", "body": None},
        ]
    )

    with patch("modules.rafail.collector.kb") as mock_kb:
        mock_kb.material_exists.return_value = False
        result = await collector.collect_rss(
            {
                "url": "http://test.com/rss",
                "name": "Test",
                "domain": "ses",
                "track": "all",
            }
        )

    assert result == 2
    assert mock_kb.add_material.call_count == 2


@pytest.mark.asyncio
async def test_collect_rss_skips_existing(collector: RafailCollector) -> None:
    collector._rss = MagicMock()
    collector._rss.fetch = AsyncMock(
        return_value=[
            {"url": "http://test.com/1", "title": "Уже есть", "body": ""},
        ]
    )

    with patch("modules.rafail.collector.kb") as mock_kb:
        mock_kb.material_exists.return_value = True
        result = await collector.collect_rss(
            {
                "url": "http://test.com/rss",
                "name": "Test",
                "domain": "ses",
                "track": "all",
            }
        )

    assert result == 0


def test_cleanup_materials(collector: RafailCollector) -> None:
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 5
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value = mock_cursor

    with patch("modules.rafail.db.connect", return_value=mock_conn):
        result = collector.cleanup_materials(days=7)

    assert result == 10  # 5 + 5 (два DELETE)
    assert mock_conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_collect_all_empty_sources(collector: RafailCollector) -> None:
    with patch("modules.rafail.collector.kb") as mock_kb, patch(
        "modules.rafail.collector.opt", return_value=""
    ):
        mock_kb.get_sources.return_value = []
        mock_kb.log_sync = MagicMock()
        result = await collector.collect_all(domain="ses")

    assert result == {}
    mock_kb.log_sync.assert_called_once()
