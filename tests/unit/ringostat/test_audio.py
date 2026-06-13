"""Тесты для AudioDownloader."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.ringostat.audio import AudioDownloader


@pytest.fixture
def downloader(tmp_path):
    with patch(
        "modules.ringostat.audio.get_settings",
        return_value=MagicMock(ringostat_auth_key=""),
    ):
        d = AudioDownloader()
        d._dir = tmp_path
        return d


@pytest.mark.asyncio
async def test_download_no_url(downloader):
    result = await downloader.download("call_1", "")
    assert result is None


@pytest.mark.asyncio
async def test_download_cached(downloader):
    cached = downloader._dir / "call_1.mp3"
    cached.write_bytes(b"fake audio")
    result = await downloader.download("call_1", "http://example.com/audio.mp3")
    assert result == cached


@pytest.mark.asyncio
async def test_download_fetches_remote(downloader):
    mock_response = MagicMock()
    mock_response.content = b"audio data"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("modules.ringostat.audio.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "modules.ringostat.audio.get_settings",
            return_value=MagicMock(ringostat_auth_key=""),
        ):
            result = await downloader.download("call_2", "http://example.com/audio.mp3")

    assert result == downloader._dir / "call_2.mp3"
    assert result.read_bytes() == b"audio data"


@pytest.mark.asyncio
async def test_download_error_returns_none(downloader):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("connection failed"))

    with patch("modules.ringostat.audio.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "modules.ringostat.audio.get_settings",
            return_value=MagicMock(ringostat_auth_key=""),
        ):
            result = await downloader.download("call_3", "http://example.com/audio.mp3")

    assert result is None


def test_cleanup_removes_file(downloader):
    f = downloader._dir / "call_1.mp3"
    f.write_bytes(b"data")
    downloader.cleanup("call_1")
    assert not f.exists()


def test_cleanup_missing_ok(downloader):
    downloader.cleanup("nonexistent")  # не должно бросать исключение


def test_get_cached_exists(downloader):
    f = downloader._dir / "call_5.mp3"
    f.write_bytes(b"x")
    assert downloader.get_cached("call_5") == f


def test_get_cached_missing(downloader):
    assert downloader.get_cached("missing") is None
