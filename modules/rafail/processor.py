"""Processor — Gemini-обработка материалов в учебный контент (RF-7).

Использует shared/llm: общий пул ключей Gemini + провайдер с safety off.
Результаты пишутся в processed со статусом pending (ждут одобрения).
Промпты — в таблице prompts (rafail.db), редактируются TG-кнопками.
"""

from __future__ import annotations

import json
import logging
import os

from modules.rafail import knowledge_base as kb
from shared.config.settings import get_settings
from shared.llm.providers import gemini as gemini_p
from shared.llm.router import gemini_pool
from shared.models.rafail import Material

logger = logging.getLogger(__name__)

MODEL = os.getenv("RAFAIL_MODEL", "gemini-2.5-flash")
MODEL_QUALITY = os.getenv(
    "RAFAIL_MODEL_QUALITY", "gemini-2.5-flash"
)  # pro недоступен на free tier


class RafailProcessor:
    """OOP-интерфейс для обработки материалов → учебный контент."""

    def __init__(self, level: str | None = None, dept: str | None = None) -> None:
        s = get_settings()
        self._model = s.rafail_model
        self._model_quality = s.rafail_model_quality
        self._level = level or kb.get_setting("active_track", "trainee")
        self._dept = dept or kb.get_setting("active_dept", "sales")

    async def _generate(self, prompt: str, quality: bool = False) -> str:
        model = self._model_quality if quality else self._model
        try:
            return await gemini_p.generate(model, prompt, gemini_pool)
        except Exception as e:
            logger.warning("[RafailProcessor] %s ошибка: %s — fallback", model, e)
            return await gemini_p.generate(self._model, prompt, gemini_pool)

    async def is_relevant(self, title: str) -> bool:
        prompt = kb.get_prompt("relevance_check").format(title=title)
        try:
            result = await self._generate(prompt)
            return "YES" in result.strip().upper()
        except Exception:
            return True

    async def make_section(self, material: Material) -> int:
        """Material pydantic модель → processed_id (pending)."""
        return await make_universal_section(
            material.id, level=self._level, dept=self._dept
        )

    async def process_batch(self, limit: int = 10) -> dict[str, object]:
        return await process_pending(limit=limit, level=self._level, dept=self._dept)


_ROLE_BY_TRACK = {
    "sales": "менеджер з продажу",
    "engineers": "інженер ПТО",
    "installers": "монтажник",
    "all": "співробітник LK Energy",
}


def load_prompt(name: str) -> str:
    """Промпт из БД (seed заполняет дефолты при init_db)."""
    return kb.get_prompt(name)


async def _generate(prompt: str, quality: bool = False) -> str:
    model = MODEL_QUALITY if quality else MODEL
    try:
        return await gemini_p.generate(model, prompt, gemini_pool)
    except Exception as e:
        logger.warning("[processor] %s недоступна (%s) — пробую %s", model, e, MODEL)
        return await gemini_p.generate(MODEL, prompt, gemini_pool)


# ── генераторы контента ───────────────────────────────────────────────────────


async def make_course_section(material_id: int, topic: str = "") -> int:
    """Материал → секция модуля курса. Возвращает processed_id (pending)."""
    mat = kb.get_material(material_id)
    if not mat:
        raise ValueError(f"Материал {material_id} не найден")
    track = mat["track"] or "all"
    prompt = load_prompt("course_section").format(
        track=track,
        role=_ROLE_BY_TRACK.get(track, _ROLE_BY_TRACK["all"]),
        topic=topic or mat["title"],
        materials=mat["raw_content"][:30000],
    )
    content = await _generate(prompt, quality=True)
    pid = kb.add_processed(
        material_id, "course_section", track, topic or mat["title"], content
    )
    logger.info("[processor] course_section #%d из материала #%d", pid, material_id)
    return pid


async def make_summary(material_id: int) -> int:
    """Материал → конспект для БЗ."""
    mat = kb.get_material(material_id)
    if not mat:
        raise ValueError(f"Материал {material_id} не найден")
    track = mat["track"] or "all"
    prompt = load_prompt("summary").format(
        track=track, content=mat["raw_content"][:30000]
    )
    content = await _generate(prompt)
    return kb.add_processed(material_id, "summary", track, mat["title"], content)


async def make_case_study(material_id: int) -> int:
    """Звонок/сделка → учебный кейс."""
    mat = kb.get_material(material_id)
    if not mat:
        raise ValueError(f"Материал {material_id} не найден")
    prompt = load_prompt("case_study").format(source_data=mat["raw_content"][:30000])
    content = await _generate(prompt)
    title = f"Кейс: {mat['title']}"
    return kb.add_processed(material_id, "case_study", "sales", title, content)


async def make_quiz(
    module_content: str, title: str, track: str = "all", count: int = 7
) -> int:
    """Контент модуля → JSON с вопросами теста. Валидирует JSON до записи."""
    prompt = (
        load_prompt("quiz_generator")
        .replace("{count}", str(count))
        .replace("{module_content}", module_content[:30000])
    )
    raw = await _generate(prompt)
    questions = parse_quiz_json(raw)
    content = json.dumps(questions, ensure_ascii=False, indent=1)
    return kb.add_processed(None, "quiz", track, f"Тест: {title}", content)


# ── Moodle XML (RF-10) ────────────────────────────────────────────────────────


def questions_to_moodle_xml(questions: list[dict], category: str = "") -> str:
    """JSON-вопросы (make_quiz) → Moodle XML для импорта в банк вопросов.

    category — путь категории банка ('$course$/Рафаил/М1'): вопросы лягут
    в свою категорию, и mod_quiz_add_random_questions сможет брать из неё.
    """
    from xml.sax.saxutils import escape

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"]

    if category:
        parts.append(
            '<question type="category"><category>'
            f"<text>{escape(category)}</text>"
            "</category></question>"
        )

    for i, q in enumerate(questions, 1):
        parts.append('<question type="multichoice">')
        parts.append(f"<name><text>{escape(q['question'][:60])} [{i}]</text></name>")
        parts.append(
            '<questiontext format="html">'
            f"<text><![CDATA[<p>{q['question']}</p>]]></text>"
            "</questiontext>"
        )
        for a in q["answers"]:
            fraction = "100" if a.get("correct") else "0"
            parts.append(f'<answer fraction="{fraction}" format="html">')
            parts.append(f"<text><![CDATA[{a['text']}]]></text>")
            if a.get("feedback"):
                parts.append(
                    f'<feedback format="html"><text><![CDATA[{a["feedback"]}]]></text></feedback>'
                )
            parts.append("</answer>")
        parts.append("<single>true</single>")
        parts.append("<shuffleanswers>true</shuffleanswers>")
        parts.append("<defaultgrade>1</defaultgrade>")
        parts.append("</question>")

    parts.append("</quiz>")
    return "\n".join(parts)


# ── утилиты ───────────────────────────────────────────────────────────────────


def parse_quiz_json(raw: str) -> list[dict]:
    """Достать JSON-массив вопросов из ответа LLM (терпимо к ```json обёрткам)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("В ответе LLM нет JSON-массива вопросов")
    questions = json.loads(text[start : end + 1])
    for q in questions:
        if "question" not in q or "answers" not in q:
            raise ValueError(f"Вопрос без обязательных полей: {q}")
        corrects = [a for a in q["answers"] if a.get("correct")]
        if len(corrects) != 1:
            raise ValueError(
                f"Вопрос должен иметь ровно 1 правильный ответ: {q['question']}"
            )
    return questions


# ── универсальная секция по карьерной матрице (RF-5) ─────────────────────────


async def make_universal_section(
    material_id: int, level: str = "", dept: str = ""
) -> int:
    """Материал → секция для уровня карьерной матрицы."""
    mat = kb.get_material(material_id)
    if not mat:
        raise ValueError(f"Материал {material_id} не найден")

    # активный уровень из settings если не указан
    if not level:
        level = kb.get_setting("active_track", "trainee")
    if not dept:
        dept = kb.get_setting("active_dept", "sales")

    prompt_tpl = kb.get_prompt("universal_section")
    instructions = json.loads(kb.get_setting("level_instructions", "{}"))
    level_instructions = instructions.get(level, instructions.get("trainee", ""))

    # русское название уровня из career_matrix
    matrix = json.loads(kb.get_setting("career_matrix", "{}"))
    level_name = level
    for dept_levels in matrix.values():
        for code, name, _ in dept_levels:
            if code == level:
                level_name = name
                break

    prompt = prompt_tpl.format(
        level_name=level_name,
        dept=dept,
        topic=mat["title"],
        level_instructions=level_instructions,
        content=mat["raw_content"][:30000],
    )
    content = await _generate(prompt, quality=True)
    pid = kb.add_processed(material_id, "course_section", dept, mat["title"], content)
    logger.info(
        "[processor] universal_section level=%s #%d из материала #%d",
        level,
        pid,
        material_id,
    )
    return pid


async def process_pending(limit: int = 10, level: str = "", dept: str = "") -> dict:
    """Пакетная обработка необработанных материалов."""
    # активные настройки
    if not level:
        level = kb.get_setting("active_track", "trainee")
    if not dept:
        dept = kb.get_setting("active_dept", "sales")

    from modules.rafail.db import connect

    with connect() as c:
        materials = c.execute(
            """
            SELECT m.id, m.title FROM materials m
            WHERE m.id NOT IN (
                SELECT DISTINCT material_id FROM processed
                WHERE material_id IS NOT NULL
            )
            ORDER BY m.collected_at DESC LIMIT ?
        """,
            (limit,),
        ).fetchall()

    results = {
        "level": level,
        "dept": dept,
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "ids": [],
    }
    for mat in materials:
        try:
            if not await is_relevant(mat["title"]):
                logger.info(
                    "[processor] пропущен нерелевантный материал #%d: %s",
                    mat["id"],
                    mat["title"][:50],
                )
                results["skipped"] += 1
                continue
            pid = await make_universal_section(mat["id"], level=level, dept=dept)
            results["processed"] += 1
            results["ids"].append(pid)
            logger.info("[processor] OK материал #%d → processed #%d", mat["id"], pid)
        except Exception as e:
            logger.error("[processor] ошибка материал #%d: %s", mat["id"], e)
            results["errors"] += 1

    return results


async def is_relevant(title: str) -> bool:
    """Быстрая проверка релевантности материала через Gemini (YES/NO)."""
    prompt = kb.get_prompt("relevance_check").format(title=title)
    try:
        result = await _generate(prompt, quality=False)
        return "YES" in result.strip().upper()
    except Exception as e:
        logger.warning(
            "[processor] is_relevant ошибка для '%s': %s — пропускаем", title, e
        )
        return True  # при ошибке — пропускаем, не блокируем пайплайн
