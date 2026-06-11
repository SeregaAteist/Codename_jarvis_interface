"""Универсальные парсеры источников: api / html / rss + dispatcher."""
from core.parsers.api import ApiParser
from core.parsers.base import BaseParser
from core.parsers.html import HtmlParser
from core.parsers.rss import RssParser

__all__ = ["BaseParser", "ApiParser", "HtmlParser", "RssParser"]
