"""Watcher локальной очереди (драйвер local).

next_pending() → запуск Claude Code → запись результата и статуса в SQLite.
НЕ активен пока CFG.EXECUTOR=ssh (живёт SSH task_watcher.sh). Запуск при переходе
на local: python -m executor.watcher
"""
from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from executor.local_queue import DB, LocalQueueExecutor
from shared.config import CFG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("local_watcher")

CLAUDE = str(Path.home() / ".local" / "bin" / "claude")
REPO_ROOT = str(CFG.DATA_DIR.parent)  # корень проекта (DATA_DIR = ROOT/data)


def _run_claude(prompt: str) -> tuple[str, bool]:
    try:
        r = subprocess.run(
            [CLAUDE, "--model", CFG.CLAUDE_MODEL, "--dangerously-skip-permissions", "--print", prompt],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
        )
        out = (r.stdout or r.stderr or "").strip()
        return out, r.returncode == 0
    except subprocess.TimeoutExpired:
        return "⏱️ TIMEOUT — превышено время обработки (600с)", False
    except Exception as e:
        return f"ошибка watcher: {e}", False


def main() -> None:
    q = LocalQueueExecutor()
    logger.info("local watcher запущен (БД=%s)", DB)
    while True:
        nxt = q.next_pending()
        if not nxt:
            time.sleep(3)
            continue
        task_id, payload = nxt
        q.mark(task_id, "running")
        prompt = payload.get("prompt") or payload.get("content") or ""
        out, ok = _run_claude(prompt)
        q.mark(task_id, "done" if ok else "failed", out)
        logger.info("задача %s → %s", task_id, "done" if ok else "failed")


if __name__ == "__main__":
    main()
