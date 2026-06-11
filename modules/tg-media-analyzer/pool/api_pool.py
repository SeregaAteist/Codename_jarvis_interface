"""Back-compat shim — пул переехал в shared/llm/key_pool.py (Фаза 3).

Старый путь оставлен до Фазы 9, чтобы не ломать импорты (напр. pipeline/deep.py).
"""
from __future__ import annotations

from shared.llm.key_pool import SimplePool  # noqa: F401

__all__ = ["SimplePool"]
