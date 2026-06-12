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
