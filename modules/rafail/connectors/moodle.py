"""MoodleConnector — Moodle REST API (RF-2).

Эндпоинт: POST {MOODLE_URL}/webservice/rest/server.php
Параметры: wstoken={token}&wsfunction={function}&moodlewsrestformat=json

Moodle отвечает 200 даже на ошибки — признак ошибки в теле:
{"exception": "...", "errorcode": "...", "message": "..."}.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.config.secrets import opt

logger = logging.getLogger(__name__)


class MoodleError(RuntimeError):
    """Ошибка Moodle API (exception в теле ответа)."""

    def __init__(self, errorcode: str, message: str):
        super().__init__(f"[{errorcode}] {message}")
        self.errorcode = errorcode


class MoodleConnector:
    def __init__(self, url: str = "", token: str = "", timeout: int = 30):
        self.url = (url or opt("MOODLE_URL")).rstrip("/")
        self.token = token or opt("MOODLE_TOKEN")
        self.timeout = timeout

    @property
    def endpoint(self) -> str:
        return f"{self.url}/webservice/rest/server.php"

    async def call(self, wsfunction: str, **params: Any) -> Any:
        """Вызов ws-функции. Плоская сериализация массивов Moodle-стилем."""
        import httpx

        data: dict[str, Any] = {
            "wstoken": self.token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        data.update(_flatten(params))

        async with httpx.AsyncClient(timeout=self.timeout) as cli:
            r = await cli.post(self.endpoint, data=data)
            r.raise_for_status()
            payload = r.json()

        if isinstance(payload, dict) and "exception" in payload:
            raise MoodleError(payload.get("errorcode", "?"), payload.get("message", ""))
        return payload

    # ── базовые операции ──────────────────────────────────────────────────────

    async def ping(self) -> dict:
        """Проверка токена: core_webservice_get_site_info.

        Возвращает {sitename, username, userid, release, functions_count}.
        """
        info = await self.call("core_webservice_get_site_info")
        return {
            "sitename": info.get("sitename"),
            "username": info.get("username"),
            "userid": info.get("userid"),
            "release": info.get("release"),
            "functions_count": len(info.get("functions", [])),
        }

    async def get_courses(self) -> list:
        return await self.call("core_course_get_courses")

    async def get_categories(self) -> list:
        return await self.call("core_course_get_categories")

    async def create_category(self, name: str, parent_id: int = 0) -> dict:
        res = await self.call(
            "core_course_create_categories",
            categories=[{"name": name, "parent": parent_id}],
        )
        return res[0] if res else {}

    async def create_course(
        self,
        title: str,
        category_id: int,
        description: str = "",
        shortname: str = "",
        summary_format: int = 1,
    ) -> dict:
        """summary_format: 1=HTML, 4=Markdown (Moodle FORMAT_MARKDOWN)."""
        res = await self.call(
            "core_course_create_courses",
            courses=[
                {
                    "fullname": title,
                    "shortname": (shortname or title)[:80],
                    "categoryid": category_id,
                    "summary": description,
                    "summaryformat": summary_format,
                }
            ],
        )
        return res[0] if res else {}

    async def update_course(self, course_id: int, **fields: Any) -> dict:
        course = {"id": course_id, **fields}
        return await self.call("core_course_update_courses", courses=[course])

    async def get_sections(self, course_id: int) -> list:
        return await self.call("core_course_get_contents", courseid=course_id)

    async def get_users(self) -> list:
        res = await self.call(
            "core_user_get_users", criteria=[{"key": "deleted", "value": "0"}]
        )
        return res.get("users", []) if isinstance(res, dict) else res

    async def enrol_user(self, user_id: int, course_id: int, role_id: int = 5) -> None:
        await self.call(
            "enrol_manual_enrol_users",
            enrolments=[{"roleid": role_id, "userid": user_id, "courseid": course_id}],
        )

    async def get_grades(self, course_id: int) -> Any:
        return await self.call("gradereport_user_get_grade_items", courseid=course_id)

    # ── квизы (RF-10) ─────────────────────────────────────────────────────────

    async def get_quizzes(self, course_id: int) -> list:
        """Квизы курса: [{id, coursemodule, name, ...}]."""
        res = await self.call("mod_quiz_get_quizzes_by_courses", courseids=[course_id])
        return res.get("quizzes", []) if isinstance(res, dict) else res

    async def upload_quiz_xml(
        self, xml_content: str, filename: str = "quiz.xml"
    ) -> int:
        """Загрузить Moodle XML в draft-зону пользователя. Возвращает draft itemid.

        Дальше itemid используется при импорте вопросов в банк
        (qformat_xml через форму импорта либо плагин на стороне Moodle).
        """
        import base64

        res = await self.call(
            "core_files_upload",
            contextlevel="user",
            instanceid=await self._own_userid(),
            component="user",
            filearea="draft",
            itemid=0,
            filepath="/",
            filename=filename,
            filecontent=base64.b64encode(xml_content.encode("utf-8")).decode(),
        )
        return int(res.get("itemid", 0)) if isinstance(res, dict) else 0

    async def add_random_questions(
        self,
        quiz_id: int,
        category_id: int,
        count: int = 1,
        include_subcategories: bool = False,
    ) -> Any:
        """Добавить в квиз N случайных вопросов из категории банка вопросов."""
        return await self.call(
            "mod_quiz_add_random_questions",
            quizid=quiz_id,
            addonpage=0,
            randomcount=count,
            categoryid=category_id,
            includesubcategories=1 if include_subcategories else 0,
        )

    async def update_slots(self, quiz_id: int, slots: list[dict]) -> Any:
        """Обновить слоты квиза (порядок/страницы/баллы)."""
        return await self.call("mod_quiz_update_slots", quizid=quiz_id, slots=slots)

    async def _own_userid(self) -> int:
        if not hasattr(self, "_userid"):
            info = await self.call("core_webservice_get_site_info")
            self._userid = int(info["userid"])
        return self._userid

    async def get_course_completion(self, course_id: int, user_id: int) -> Any:
        return await self.call(
            "core_completion_get_course_completion_status",
            courseid=course_id,
            userid=user_id,
        )

    async def get_full_structure(self) -> dict:
        """Получить полную структуру Moodle — категории, курсы, секции."""
        categories = await self.call("core_course_get_categories", criteria=[])
        courses = await self.call("core_course_get_courses")

        structure: dict[str, Any] = {"categories": {}, "courses": {}}

        for cat in categories:
            structure["categories"][cat["id"]] = {
                "name": cat["name"],
                "parent": cat["parent"],
                "courses": [],
            }

        for course in courses:
            cat_id = course.get("categoryid", 0)
            if cat_id in structure["categories"]:
                structure["categories"][cat_id]["courses"].append(course["id"])

            sections = await self.get_sections(course["id"])
            structure["courses"][course["id"]] = {
                "name": course["fullname"],
                "category": cat_id,
                "sections": len(sections),
                "modules": sum(len(s.get("modules", [])) for s in sections),
            }

        return structure

    async def export_structure_yaml(self, output_path: str) -> None:
        """Экспортировать структуру Moodle в YAML файл."""
        from pathlib import Path as _Path

        import yaml

        structure = await self.get_full_structure()
        _Path(output_path).write_text(
            yaml.dump(structure, allow_unicode=True),
            encoding="utf-8",
        )


def _flatten(params: dict, prefix: str = "") -> dict:
    """Moodle-стиль сериализации: courses[0][fullname]=X, criteria[0][key]=Y."""
    flat: dict[str, Any] = {}
    for key, value in params.items():
        full = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, full))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    flat.update(_flatten(item, f"{full}[{i}]"))
                else:
                    flat[f"{full}[{i}]"] = item
        else:
            flat[full] = value
    return flat
