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

    async def create_course(self, title: str, category_id: int, description: str = "") -> dict:
        res = await self.call(
            "core_course_create_courses",
            courses=[{
                "fullname": title,
                "shortname": title[:80],
                "categoryid": category_id,
                "summary": description,
                "summaryformat": 1,
            }],
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

    async def get_course_completion(self, course_id: int, user_id: int) -> Any:
        return await self.call(
            "core_completion_get_course_completion_status",
            courseid=course_id, userid=user_id,
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
