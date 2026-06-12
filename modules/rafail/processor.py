"""Processor — Gemini-обработка материалов в учебный контент (RF-7).

Использует shared/llm: общий пул ключей Gemini + провайдер с safety off.
Результаты пишутся в processed со статусом pending (ждут одобрения).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from shared.llm.providers import gemini as gemini_p
from shared.llm.router import gemini_pool
from modules.rafail import knowledge_base as kb

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

MODEL = "gemini-2.5-flash"
MODEL_QUALITY = "gemini-2.5-pro"   # course_section: качество важнее скорости

_ROLE_BY_TRACK = {
    "sales": "менеджер з продажу",
    "engineers": "інженер ПТО",
    "installers": "монтажник",
    "all": "співробітник LK Energy",
}


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


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
    pid = kb.add_processed(material_id, "course_section", track, topic or mat["title"], content)
    logger.info("[processor] course_section #%d из материала #%d", pid, material_id)
    return pid


async def make_summary(material_id: int) -> int:
    """Материал → конспект для БЗ."""
    mat = kb.get_material(material_id)
    if not mat:
        raise ValueError(f"Материал {material_id} не найден")
    track = mat["track"] or "all"
    prompt = load_prompt("summary").format(track=track, content=mat["raw_content"][:30000])
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


async def make_quiz(module_content: str, title: str, track: str = "all", count: int = 7) -> int:
    """Контент модуля → JSON с вопросами теста. Валидирует JSON до записи."""
    prompt = load_prompt("quiz_generator").replace("{count}", str(count)) \
                                          .replace("{module_content}", module_content[:30000])
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
    questions = json.loads(text[start:end + 1])
    for q in questions:
        if "question" not in q or "answers" not in q:
            raise ValueError(f"Вопрос без обязательных полей: {q}")
        corrects = [a for a in q["answers"] if a.get("correct")]
        if len(corrects) != 1:
            raise ValueError(f"Вопрос должен иметь ровно 1 правильный ответ: {q['question']}")
    return questions
