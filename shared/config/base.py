"""Базовый слой конфига: пути, лог-уровни, общие лимиты и дефолты.

Слой 1 из 3. Не содержит секретов (см. secrets.py) и не привязан к
конкретному боту (см. modules/<name>.yaml). Общий фундамент для всех ботов.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Корень проекта = на 2 уровня выше shared/config/base.py
ROOT: Path = Path(os.getenv("JARVIS_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR: Path = Path(__file__).resolve().parent
MODULES_DIR: Path = CONFIG_DIR / "modules"

DATA_DIR: Path = Path(os.getenv("DATA_DIR", ROOT / "data"))
LOGS_DIR: Path = ROOT / "logs"
TASKS_DIR: Path = Path(os.getenv("TASKS_DIR", ROOT / "tasks"))

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Общие дефолты — переопределяются в modules/<name>.yaml или через .env.
DEFAULTS: dict[str, Any] = {
    "batch_timeout": 8,
    "max_image_size": 4 * 1024 * 1024,
    "gemini_model": "gemini-2.5-flash",
    "gemini_fallback_model": "gemini-2.5-pro",
    "claude_model": "claude-fable-5",
    "ollama_model": "llama3.2",
    "ollama_host": "http://localhost:11434",
    "executor": "ssh",  # default — рабочий SSH-поток; local включается отдельным шагом
}


def load_module_yaml(name: str) -> dict[str, Any]:
    """Прочитать modules/<name>.yaml бота. Отсутствует → пустой dict."""
    p = MODULES_DIR / f"{name}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
