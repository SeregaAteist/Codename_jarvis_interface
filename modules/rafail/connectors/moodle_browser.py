"""MoodleBrowser — управление Moodle через Playwright (действия недоступные через API)."""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)


class MoodleBrowser:
    """Playwright-коннектор для действий в Moodle недоступных через REST API."""

    def __init__(self) -> None:
        self._url = os.getenv("MOODLE_URL", "https://my.lk-energy.com.ua")
        self._user = os.getenv("MOODLE_ADMIN_USER", "")
        self._pass = os.getenv("MOODLE_ADMIN_PASS", "")

    async def _get_page(self, playwright):
        """Создать страницу и залогиниться."""
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{self._url}/login/index.php")
        await page.fill("#username", self._user)
        await page.fill("#password", self._pass)
        await page.click("#loginbtn")
        await page.wait_for_load_state("networkidle")
        return browser, page

    async def _get_sesskey(self, page) -> str:
        """Получить sesskey из страницы управления курсами."""
        await page.goto(f"{self._url}/course/management.php")
        await page.wait_for_load_state("networkidle")
        html = await page.content()
        match = re.search(r"sesskey=([A-Za-z0-9]+)", html)
        if not match:
            raise RuntimeError("sesskey не найден — возможно логин не прошёл")
        return match.group(1)

    async def set_category_visibility(self, category_id: int, visible: bool) -> None:
        """Скрыть или показать категорию."""
        from playwright.async_api import async_playwright

        action = "showcategory" if visible else "hidecategory"
        async with async_playwright() as p:
            browser, page = await self._get_page(p)
            try:
                sesskey = await self._get_sesskey(page)
                url = (
                    f"{self._url}/course/management.php"
                    f"?categoryid={category_id}&sesskey={sesskey}&action={action}"
                )
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                status = "показана" if visible else "скрыта"
                logger.info("[moodle_browser] категория %d %s", category_id, status)
            finally:
                await browser.close()

    async def set_course_visibility(self, course_id: int, visible: bool) -> None:
        """Скрыть или показать курс."""
        from playwright.async_api import async_playwright

        action = "show" if visible else "hide"
        async with async_playwright() as p:
            browser, page = await self._get_page(p)
            try:
                sesskey = await self._get_sesskey(page)
                url = (
                    f"{self._url}/course/management.php"
                    f"?courseid={course_id}&sesskey={sesskey}&action={action}course"
                )
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                logger.info("[moodle_browser] курс %d %s", course_id, action)
            finally:
                await browser.close()

    async def move_course_to_category(
        self, course_id: int, target_category_id: int
    ) -> None:
        """Переместить курс в другую категорию."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, page = await self._get_page(p)
            try:
                await page.goto(f"{self._url}/course/edit.php?id={course_id}")
                await page.wait_for_load_state("networkidle")
                await page.select_option("#id_category", str(target_category_id))
                await page.click('#id_saveanddisplay, [name="saveanddisplay"]')
                await page.wait_for_load_state("networkidle")
                logger.info(
                    "[moodle_browser] курс %d → категория %d",
                    course_id,
                    target_category_id,
                )
            finally:
                await browser.close()

    async def reorder_courses(self, category_id: int, course_order: list[int]) -> None:
        """Упорядочить курсы в категории."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, page = await self._get_page(p)
            try:
                sesskey = await self._get_sesskey(page)
                for position, course_id in enumerate(course_order, 1):
                    url = (
                        f"{self._url}/course/management.php"
                        f"?categoryid={category_id}&sesskey={sesskey}"
                        f"&action=movecourseafter&courseid={course_id}"
                        f"&aftercourseid=0"
                    )
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")
                logger.info(
                    "[moodle_browser] курсы в категории %d упорядочены", category_id
                )
            finally:
                await browser.close()


# singleton
_browser: MoodleBrowser | None = None


def get_moodle_browser() -> MoodleBrowser:
    global _browser
    if _browser is None:
        _browser = MoodleBrowser()
    return _browser
