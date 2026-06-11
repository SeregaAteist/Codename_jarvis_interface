"""Локальная SQLite-очередь задач (драйвер local).

Строится РЯДОМ с SSH-потоком; по умолчанию НЕ активна (CFG.EXECUTOR=ssh).
БД: <DATA_DIR>/sqlite/jarvis.db, таблица tasks(id, payload, status, result,
created_at, updated_at). Async-интерфейс submit/status (TaskExecutor) +
sync-ядро (next_pending/mark/result) для watcher'а.
"""
from __future__ import annotations

import json
import sqlite3
import time

from executor.base import TaskExecutor
from shared.config import CFG

DB = CFG.DATA_DIR / "sqlite" / "jarvis.db"


class LocalQueueExecutor(TaskExecutor):
    def __init__(self) -> None:
        DB.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )"""
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(DB, timeout=10)

    # --- async-интерфейс TaskExecutor ---
    async def submit(self, task: dict) -> int:
        return self._submit(task)

    async def status(self, task_id) -> str:
        return self._status(task_id)

    # --- sync-ядро (для watcher'а / прямого использования) ---
    def _submit(self, task: dict) -> int:
        now = time.time()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO tasks(payload, status, created_at, updated_at) VALUES(?, 'pending', ?, ?)",
                (json.dumps(task, ensure_ascii=False), now, now),
            )
            return cur.lastrowid

    def _status(self, task_id) -> str:
        with self._conn() as c:
            row = c.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
            return row[0] if row else "unknown"

    def result(self, task_id):
        with self._conn() as c:
            row = c.execute("SELECT result FROM tasks WHERE id=?", (task_id,)).fetchone()
            return row[0] if row else None

    def next_pending(self) -> "tuple[int, dict] | None":
        with self._conn() as c:
            row = c.execute(
                "SELECT id, payload FROM tasks WHERE status='pending' ORDER BY id LIMIT 1"
            ).fetchone()
            return (row[0], json.loads(row[1])) if row else None

    def mark(self, task_id, status: str, result: str | None = None) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE tasks SET status=?, result=COALESCE(?, result), updated_at=? WHERE id=?",
                (status, result, time.time(), task_id),
            )
