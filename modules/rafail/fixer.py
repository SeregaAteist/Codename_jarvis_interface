"""fix_pending_modules — первый pipeline Рафаила (RF-9, ПРИОРИТЕТ 1).

М1..М5 в Drive имеют файлы правок «++». Цикл по модулю:
  1. найти в папке курса файл модуля и файл правок (++)
  2. прочитать оба
  3. Gemini сливает правки в новую версию (фирменный стиль)
  4. processed(pending) → одобрение владельца (approver)
  5. approved → upload новой версии в Drive (+ NotebookLM папка, если настроена)
  6. след в moodle_map + sync_log

Moodle-страницы обновляются вручную/через RF-10+ — у токена нет прав
на создание контента модулей (см. RF-2).
"""
from __future__ import annotations

import logging
import re

from modules.rafail import knowledge_base as kb
from modules.rafail import processor
from modules.rafail.approver import RafailApprover
from modules.rafail.connectors.drive import DriveConnector

logger = logging.getLogger(__name__)

PENDING_MODULES = ["М1", "М2", "М3", "М4", "М5"]   # ТРЕБА ВЛИТИ ++ (ТЗ)
_PLUS_MARK = "++"


def match_module_files(files: list[dict], module: str) -> tuple[dict | None, dict | None]:
    """В списке файлов папки найти (файл модуля, файл правок ++).

    Модуль ищем по вхождению 'М1'/'M1' (кириллица/латиница) в имени,
    правки — файл модуля, содержащий '++'.
    """
    cyr = module                      # М1 (кириллица из ТЗ)
    lat = "M" + module[1:]            # M1 (латиница)
    pattern = re.compile(rf"(?:{cyr}|{lat})(?:\b|[._\s-])", re.IGNORECASE)

    module_file = None
    plus_file = None
    for f in files:
        name = f.get("name", "")
        if not pattern.search(name):
            continue
        if _PLUS_MARK in name:
            plus_file = f
        elif module_file is None:
            module_file = f
    return module_file, plus_file


async def fix_module(
    module: str,
    drive: DriveConnector,
    approver: RafailApprover,
    folder_key: str = "course_ses",
) -> dict:
    """Полный цикл слияния правок одного модуля. Возвращает итог."""
    files = await drive.list_folder(drive.FOLDER_IDS[folder_key])
    module_file, plus_file = match_module_files(files, module)

    if not module_file:
        kb.log_sync("fix_module", "skip", f"{module}: файл модуля не найден")
        return {"module": module, "status": "not_found"}
    if not plus_file:
        kb.log_sync("fix_module", "skip", f"{module}: файл ++ не найден")
        return {"module": module, "status": "no_fixes"}

    module_content = await drive.read_file(module_file["id"])
    fixes_content = await drive.read_file(plus_file["id"])

    # Gemini сливает правки
    prompt = processor.load_prompt("module_fix").format(
        module_content=module_content[:60000],
        fixes_content=fixes_content[:30000],
    )
    merged = await processor._generate(prompt, quality=True)

    # материал-источник + processed на одобрение
    mid = kb.add_material(
        domain="internal", track="sales",
        title=f"{module}: слияние правок ++",
        raw_content=fixes_content[:10000],
        source_url=f"drive://{plus_file['id']}", source_type="drive",
    )
    pid = kb.add_processed(mid, "course_section", "sales",
                           f"{module} — новая версия (++ влиты)", merged)

    decision = await approver.submit(pid, sources_count=2)
    if decision != "approved":
        return {"module": module, "status": decision, "processed_id": pid}

    # upload новой версии в Drive
    new_name = f"{module_file['name'].rsplit('.', 1)[0]}_v2_merged.md"
    uploaded = await drive.upload_file(merged, new_name, drive.FOLDER_IDS[folder_key])
    kb.map_moodle(pid, drive_file_id=uploaded.get("id", ""))
    kb.mark_uploaded(pid)
    kb.log_sync("fix_module", "ok", f"{module} → {uploaded.get('id')}")
    logger.info("[fixer] %s: новая версия залита (%s)", module, uploaded.get("id"))
    return {"module": module, "status": "uploaded",
            "processed_id": pid, "drive_file_id": uploaded.get("id")}


async def fix_pending_modules(
    drive: DriveConnector | None = None,
    approver: RafailApprover | None = None,
    modules: list[str] | None = None,
) -> list[dict]:
    """Пройтись по М1..М5. Каждый модуль — отдельное одобрение владельца."""
    drive = drive or DriveConnector()
    if approver is None:
        raise ValueError("fix_pending_modules: нужен approver (TG-привязка)")
    results = []
    for module in modules or PENDING_MODULES:
        try:
            results.append(await fix_module(module, drive, approver))
        except Exception as e:  # noqa: BLE001
            logger.error("[fixer] %s: %s", module, e)
            kb.log_sync("fix_module", "error", f"{module}: {e}")
            results.append({"module": module, "status": "error", "error": str(e)})
    return results
