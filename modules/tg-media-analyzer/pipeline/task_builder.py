"""Task Builder — builds Claude Code task from media analysis."""

from __future__ import annotations

TASK_TEMPLATE = """# JARVIS Task — {title}

## Контекст
Проект: ~/Projects/jarvis/
Стек: MacBook Air M2, Python 3.11, Electron + React, FastAPI, ChromaDB, Groq/Gemini/Claude API
Структура: core/, agents/, connectors/, pool/, hud/, modules/

## Анализ медиаконтента
{analysis}

## Задача
На основе анализа выше — реализовать описанную функциональность в проекте JARVIS.

## Требования
1. Следовать существующей архитектуре проекта
2. Новые агенты наследовать от agents/base.py BaseAgent
3. Секреты только через .env
4. shell=False везде где subprocess
5. Добавить __init__.py если создаёшь новый модуль
6. После реализации — git commit с описанием

## Шаги выполнения
{steps}

## Результат
После выполнения отправь краткий отчёт:
- Что создано/изменено
- Команда для запуска
- Возможные проблемы
"""


def build_task(title: str, analysis: str, steps: str = "") -> str:
    if not steps:
        steps = "Определить самостоятельно на основе анализа выше."
    return TASK_TEMPLATE.format(
        title=title,
        analysis=analysis,
        steps=steps,
    )
