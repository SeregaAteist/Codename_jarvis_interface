"""generate_quizzes — пайплайн тестов для модулей курса (RF-10, ПРИОРИТЕТ 2).

Стратегия (права токена подтверждены: core_files_upload,
mod_quiz_add_random_questions, mod_quiz_update_slots):

  1. Контент модуля → make_quiz (Gemini, JSON с валидацией)
  2. Одобрение владельца (паттерн Капитана)
  3. JSON → Moodle XML (questions_to_moodle_xml, с категорией банка)
  4. core_files_upload → draft itemid (XML готов к импорту в банк вопросов)
  5. Если в rafail.yaml задан quiz_id+category_id модуля →
     mod_quiz_add_random_questions наполняет квиз из категории

Квиз в Moodle создаётся вручную один раз на модуль; его ID — в
shared/config/modules/rafail.yaml (секция rafail.quizzes).
"""
from __future__ import annotations

import json
import logging

import yaml
from pathlib import Path

from modules.rafail import knowledge_base as kb
from modules.rafail import processor
from modules.rafail.approver import RafailApprover
from modules.rafail.connectors.moodle import MoodleConnector

logger = logging.getLogger(__name__)

_RAFAIL_YAML = Path(__file__).parent.parent.parent / "shared" / "config" / "modules" / "rafail.yaml"


def quiz_map() -> dict:
    """Секция rafail.quizzes из rafail.yaml: {М1: {quiz_id, category_id}, ...}."""
    data = yaml.safe_load(_RAFAIL_YAML.read_text(encoding="utf-8")) or {}
    return (data.get("rafail") or {}).get("quizzes") or {}


def quiz_questions_count() -> int:
    data = yaml.safe_load(_RAFAIL_YAML.read_text(encoding="utf-8")) or {}
    return int((data.get("rafail") or {}).get("quiz_questions", 7))


async def generate_quiz_for_module(
    module: str,
    module_content: str,
    approver: RafailApprover,
    moodle: MoodleConnector | None = None,
    track: str = "all",
) -> dict:
    """Полный цикл теста одного модуля. Возвращает итог со статусом."""
    moodle = moodle or MoodleConnector()
    count = quiz_questions_count()

    # 1. генерация вопросов (валидация JSON внутри make_quiz)
    pid = await processor.make_quiz(module_content, module, track=track, count=count)

    # 2. одобрение владельца
    decision = await approver.submit(pid, sources_count=1)
    if decision != "approved":
        return {"module": module, "status": decision, "processed_id": pid}

    # 3. JSON → Moodle XML с категорией банка вопросов
    questions = json.loads(kb.get_processed(pid)["content"])
    category = f"$course$/Рафаил/{module}"
    xml = processor.questions_to_moodle_xml(questions, category=category)

    # 4. upload XML в draft
    itemid = await moodle.upload_quiz_xml(xml, filename=f"quiz_{module}.xml")
    kb.log_sync("quiz_upload", "ok", f"{module}: draft itemid={itemid}")

    result = {"module": module, "status": "uploaded", "processed_id": pid,
              "draft_itemid": itemid, "questions": len(questions)}

    # 5. автопривязка к квизу, если ID известны
    qm = quiz_map().get(module) or {}
    if qm.get("quiz_id") and qm.get("category_id"):
        await moodle.add_random_questions(
            int(qm["quiz_id"]), int(qm["category_id"]), count=len(questions)
        )
        kb.map_moodle(pid, moodle_activity_id=int(qm["quiz_id"]))
        result["quiz_id"] = qm["quiz_id"]
        result["status"] = "attached"
        kb.log_sync("quiz_attach", "ok", f"{module}: quiz={qm['quiz_id']}")

    kb.mark_uploaded(pid)
    return result


async def generate_quizzes(
    modules_content: dict[str, str],
    approver: RafailApprover,
    moodle: MoodleConnector | None = None,
) -> list[dict]:
    """Тесты для нескольких модулей: {module: content} → итоги по каждому."""
    moodle = moodle or MoodleConnector()
    results = []
    for module, content in modules_content.items():
        try:
            results.append(await generate_quiz_for_module(module, content, approver, moodle))
        except Exception as e:  # noqa: BLE001
            logger.error("[quizzer] %s: %s", module, e)
            kb.log_sync("quiz", "error", f"{module}: {e}")
            results.append({"module": module, "status": "error", "error": str(e)})
    return results
