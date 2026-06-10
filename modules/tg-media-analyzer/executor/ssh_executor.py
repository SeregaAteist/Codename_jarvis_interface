"""SSH Executor — all Claude calls go through local watcher."""
from __future__ import annotations
import asyncio
import logging
import os
import uuid

import config  # noqa: F401 — импорт гарантирует, что .env уже загружен (load_dotenv)

logger = logging.getLogger(__name__)

# Инфраструктура читается ТОЛЬКО из окружения/.env — в исходниках публичного репо
# никаких IP/имён/путей. Пустой SSH_HOST = исполнитель отключён (см. guard ниже).
SSH_HOST  = os.environ.get("SSH_HOST",  "")
SSH_USER  = os.environ.get("SSH_USER",  "")
SSH_KEY   = os.environ.get("SSH_KEY",   os.path.expanduser("~/.ssh/jarvis_bot"))
HOME      = os.environ.get("SSH_HOME",  os.path.expanduser("~"))
TASKS_DIR = os.environ.get("TASKS_DIR", os.path.join(os.path.expanduser("~"), "Projects/jarvis/tasks"))

PLAN_PROMPT = """Ты получил задачу. НЕ выполняй её — только составь план.

Формат:
## План выполнения
**Цель:** (одна строка)
**Шаги:**
1. [действие] — [файл/команда]
**Файлы:** (будут созданы/изменены)
**Зависимости:** (если нужны)
**Риски:** (если есть)

Задача:
{task}"""

EXECUTE_PROMPT = """Выполни задачу полностью и автономно. Не задавай вопросов.
После выполнения напиши отчёт: что создано/изменено, команда для запуска.

Задача:
{task}"""


async def get_plan(task_content: str) -> str:
    prompt = PLAN_PROMPT.format(task=task_content)
    return await _run_via_watcher(prompt, timeout=120)


async def execute_task(task_content: str) -> str:
    prompt = EXECUTE_PROMPT.format(task=task_content)
    return await _run_via_watcher(prompt, timeout=600)


async def _run_via_watcher(prompt: str, timeout: int = 300) -> str:
    """Write task for watcher, poll for result."""
    if not SSH_HOST:
        return ("⚠️ SSH-исполнитель не настроен: задайте SSH_HOST (и SSH_USER) в .env. "
                "Инфраструктура намеренно не хранится в исходниках публичного репо.")
    task_id = uuid.uuid4().hex[:8]
    task_file = f"{TASKS_DIR}/pending/TASK_{task_id}.md"
    result_file = f"{TASKS_DIR}/done/TASK_{task_id}.result"

    await _write_file(task_file, prompt)

    # Poll every 3s until result appears
    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(3)
        elapsed += 3
        exists = await _ssh(f"test -f {result_file} && echo yes || echo no", timeout=10)
        if exists.strip() == "yes":
            result = await _ssh(f"cat {result_file}", timeout=15)
            return result or "✅ Выполнено (нет вывода)"

    return f"⚠️ Таймаут {timeout}с — проверьте watcher.log"


async def _write_file(remote_path: str, content: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ssh",
        "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-l", SSH_USER,
        SSH_HOST,
        f"cat > {remote_path}",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(proc.communicate(input=content.encode()), timeout=15)
    except asyncio.TimeoutError:
        proc.kill()


async def _ssh(cmd: str, timeout: int = 30) -> str:
    proc = await asyncio.create_subprocess_exec(
        "ssh",
        "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-l", SSH_USER,
        SSH_HOST,
        f"export HOME={HOME} && {cmd}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode().strip() or stderr.decode().strip()
    except asyncio.TimeoutError:
        proc.kill()
        return f"⚠️ Таймаут {timeout}с"
