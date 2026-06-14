"""Агенты JARVIS — ленивый импорт (PEP 562).

`import agents` НЕ тянет тяжёлые зависимости отдельных агентов (bs4, google-genai,
и т.п.) — конкретный класс подгружается только при обращении к нему. Это нужно для
мульти-venv архитектуры: каждый бот держит лишь свои зависимости, а сам пакет
agents остаётся импортируемым везде.
"""

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS: dict[str, str] = {
    "OllamaAgent": "agents.ollama",
    "GroqAgent": "agents.groq",
    "GeminiAgent": "agents.gemini",
    "XAIAgent": "agents.xai",
    "ClaudeAgent": "agents.claude",
    "BrowserAgent": "agents.browser",
    "MorningAgent": "agents.morning",
    "WeatherAgent": "agents.weather",
    "RSSAgent": "agents.rss",
    "TerminalAgent": "agents.terminal",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Ленивая подгрузка класса агента по требованию (PEP 562)."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'agents' has no attribute '{name}'")
    return getattr(import_module(target), name)


def __dir__() -> list[str]:
    return sorted(__all__)


if TYPE_CHECKING:  # подсказки для IDE/статанализа, в рантайме не исполняются
    from agents.browser import BrowserAgent
    from agents.claude import ClaudeAgent
    from agents.gemini import GeminiAgent
    from agents.groq import GroqAgent
    from agents.morning import MorningAgent
    from agents.ollama import OllamaAgent
    from agents.rss import RSSAgent
    from agents.terminal import TerminalAgent
    from agents.weather import WeatherAgent
    from agents.xai import XAIAgent
