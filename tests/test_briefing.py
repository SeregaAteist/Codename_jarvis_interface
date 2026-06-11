"""Smoke брифинга: парсинг RSS (24ч-фильтр), summarizer на пустом, formatter."""
import asyncio
from datetime import datetime, timezone

from core.briefing.formatter import format_briefing
from core.briefing.reddit_rss import _parse_feed
from core.briefing.summarizer import summarize_news

_NOW = datetime.now(timezone.utc).isoformat()

_SAMPLE = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>New LLM released</title>
    <link href="https://reddit.com/x"/>
    <published>{_NOW}</published>
  </entry>
  <entry>
    <title>Old news</title>
    <link href="https://reddit.com/y"/>
    <published>2020-01-01T00:00:00+00:00</published>
  </entry>
</feed>"""


def test_parse_feed_24h_filter():
    posts = _parse_feed(_SAMPLE, "artificial", limit=5, hours=24)
    assert len(posts) == 1  # старый отфильтрован
    assert posts[0]["title"] == "New LLM released"
    assert posts[0]["subreddit"] == "artificial"
    assert posts[0]["url"] == "https://reddit.com/x"


def test_parse_feed_bad_xml():
    assert _parse_feed("не xml", "x") == []  # не падает


def test_summarizer_empty():
    r = asyncio.run(summarize_news([]))
    assert r == "Новостей за последние 24ч не найдено."  # без вызова LLM


def test_formatter():
    msg = format_briefing("• тема 1\n• тема 2", 3)
    assert "🌅" in msg and "(3 постов" in msg and "тема 1" in msg
    assert "Источники" in msg
