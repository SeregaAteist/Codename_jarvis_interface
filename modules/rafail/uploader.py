"""Uploader — выгрузка одобренного контента в Moodle (RF-8).

Стратегия: НЕ трогаем существующие курсы — Рафаил строит собственную
структуру (категория «Рафаил — {dept} — {level}» + курс), и контент
льётся туда. ID созданных объектов — в sync_log/настройках.
"""
from __future__ import annotations

import json
import logging

from modules.rafail import knowledge_base as kb
from modules.rafail.connectors.moodle import MoodleConnector

logger = logging.getLogger(__name__)


async def create_course_structure(dept: str, level: str,
                                  moodle: MoodleConnector | None = None) -> dict:
    """Создать категорию + курс в Moodle для нового трека (идемпотентно).

    Повторный вызов с теми же dept/level вернёт существующие ID из settings.
    """
    m = moodle or MoodleConnector()
    key = f"moodle_structure:{dept}:{level}"

    cached = kb.get_setting(key, "")
    if cached:
        return json.loads(cached)

    cat_name = f"Рафаил — {dept} — {level}"
    # категория: поискать существующую, иначе создать
    cat = next(
        (c for c in await m.get_categories() if c.get("name") == cat_name),
        None,
    )
    if cat is None:
        cat = await m.create_category(cat_name, parent_id=0)

    course = await m.create_course(
        title=f"{level} | {dept}",
        category_id=cat["id"],
        description=f"Автоматически создан Рафаилом. Трек: {dept}, Уровень: {level}",
    )

    result = {"category": {"id": cat["id"], "name": cat_name},
              "course": {"id": course.get("id"), "shortname": course.get("shortname")}}
    kb.set_setting(key, json.dumps(result, ensure_ascii=False))
    kb.log_sync("create_structure", "ok", f"{dept}/{level} → course={course.get('id')}")
    logger.info("[uploader] структура %s/%s: категория %s, курс %s",
                dept, level, cat["id"], course.get("id"))
    return result


async def upload_to_moodle(processed_id: int,
                           moodle: MoodleConnector | None = None) -> dict:
    """RF-9: одобренная секция → Moodle (идемпотентно по moodle_map).

    У токена нет WS-функции создания page activity (в ядре Moodle её нет),
    поэтому секция публикуется отдельным курсом в категории Рафаила:
    контент — в summary курса, summaryformat=4 (Markdown, Moodle рендерит сам).
    """
    existing = kb.get_moodle_map(processed_id)
    if existing:
        return {"course_id": existing[0]["moodle_course_id"], "already": True}

    p = kb.get_processed(processed_id)
    if not p:
        raise ValueError(f"processed {processed_id} не найден")

    m = moodle or MoodleConnector()
    dept = kb.get_setting("active_dept", "sales")
    level = kb.get_setting("active_track", "trainee")
    structure = await create_course_structure(dept, level, m)
    cat_id = structure["category"]["id"]

    course = await m.create_course(
        title=p["title"][:120],
        category_id=cat_id,
        description=p.get("content") or "",
        shortname=f"raf-{processed_id}-{p['title'][:50]}",
        summary_format=4,
    )
    course_id = int(course.get("id", 0))

    kb.map_moodle(processed_id, moodle_course_id=course_id)
    kb.mark_uploaded(processed_id)
    kb.log_sync("upload", "ok", f"processed={processed_id} → course={course_id}")
    logger.info("[uploader] processed=%d залит: курс %d (категория %d)",
                processed_id, course_id, cat_id)
    return {"course_id": course_id, "category_id": cat_id, "already": False}
