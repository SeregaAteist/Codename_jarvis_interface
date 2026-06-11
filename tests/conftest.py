"""Pytest-конфиг: пути для импорта shared/core/infra и модуля tg-media-analyzer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                                  # shared, core, infra
sys.path.insert(0, str(ROOT / "modules" / "tg-media-analyzer"))  # config, executor, pipeline, bot
