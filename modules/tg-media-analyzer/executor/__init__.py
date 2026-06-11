"""Пакет исполнителей задач. Фабрика get_executor() по CFG.EXECUTOR.

default = ssh (рабочий SSH-watcher). local = SQLite-очередь (включается отдельно).
"""
from __future__ import annotations

from shared.config import CFG
from executor.base import TaskExecutor


def get_executor() -> TaskExecutor:
    if CFG.EXECUTOR == "local":
        from executor.local_queue import LocalQueueExecutor
        return LocalQueueExecutor()
    from executor.ssh_executor import SshExecutor
    return SshExecutor()
