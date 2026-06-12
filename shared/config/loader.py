"""Единая точка чтения конфига JARVIS.

Читает jarvis.yaml (кросс-модульное: порты, модели, логирование) и
подмешивает modules/<name>.yaml под services.<name> — единый доступ
без дублирования данных. Записи services.* из jarvis.yaml имеют приоритет.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_PATH = CONFIG_DIR / "jarvis.yaml"
MODULES_DIR = CONFIG_DIR / "modules"


@lru_cache(maxsize=1)
def load() -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    services = cfg.setdefault("services", {})
    for p in sorted(MODULES_DIR.glob("*.yaml")):
        module_cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        # jarvis.yaml может дополнять модульный конфиг, но не затирается им
        merged = {**module_cfg, **services.get(p.stem, {})}
        services[p.stem] = merged
    return cfg


def get(key: str, default=None):
    """Точечный доступ: get('ports.api') → 7734, get('services.kommo.domain')."""
    val = load()
    for part in key.split("."):
        if not isinstance(val, dict):
            return default
        val = val.get(part, default)
    return val
