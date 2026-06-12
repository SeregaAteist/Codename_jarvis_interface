"""RafailAgent — корпоративная база знаний LK Energy Group (RF-11).

Оркестрирует полный pipeline: сбор → обработка (Gemini) → одобрение
владельца → заливка (Drive/Moodle/NotebookLM). Зависимости (approver,
drive, moodle) инжектируются ботом при старте; без approver операции
APPROVE-уровня возвращают понятный отказ.

Режимы (паттерн Капитана):
  AUTO    — чтение/сбор/синхронизация → выполняется сразу, отчёт владельцу
  APPROVE — генерация/изменение контента → план → кнопки → ожидание
"""
from __future__ import annotations

import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

# Долгие операции: ожидание одобрения владельца — до 24 часов.
_LONG_TIMEOUT = 25 * 3600


class RafailAgent(BaseAgent):
    name = "rafail"
    icon = "🧠"
    capabilities = [
        "knowledge_collect",
        "course_create",
        "course_update",
        "quiz_create",
        "case_study_create",
        "notebooklm_update",
        "progress_report",
        "knowledge_search",
        "module_fix",
    ]

    def __init__(self, approver=None, drive=None, moodle=None) -> None:
        super().__init__(timeout=_LONG_TIMEOUT, retries=0)
        self.approver = approver
        self.drive = drive
        self.moodle = moodle

    # ── BaseAgent-контракт ────────────────────────────────────────────────────

    async def execute(self, task: str) -> str:
        """Текстовая команда → метод. Используется через registry.dispatch."""
        cmd, _, arg = task.strip().partition(" ")
        cmd = cmd.lower()
        if cmd in ("collect", "daily_collect", "knowledge_collect"):
            return self._fmt_collect(await self.daily_collect())
        if cmd in ("fix", "fix_modules", "module_fix"):
            return self._fmt_fix(await self.fix_pending_modules(arg.split() if arg else None))
        if cmd in ("search", "knowledge_search"):
            return await self.answer_knowledge_query(arg)
        if cmd in ("progress", "progress_report"):
            return await self.generate_progress_report()
        if cmd in ("crm", "sync_crm"):
            return await self.sync_from_crm()
        return f"Рафаил: неизвестная команда '{cmd}'"

    def _require_approver(self) -> None:
        if self.approver is None:
            raise RuntimeError("Рафаил: операция требует одобрения — approver не подключён")

    # ── APPROVE-режим ─────────────────────────────────────────────────────────

    async def fix_pending_modules(self, modules: list[str] | None = None) -> list[dict]:
        """ПРИОРИТЕТ 1: влить ++ в М1-М5 (Drive → Gemini → одобрение → upload)."""
        self._require_approver()
        from modules.rafail.fixer import fix_pending_modules
        from modules.rafail.connectors.drive import DriveConnector

        drive = self.drive or DriveConnector()
        return await fix_pending_modules(drive=drive, approver=self.approver, modules=modules)

    async def generate_quizzes(self, modules_content: dict[str, str]) -> list[dict]:
        """ПРИОРИТЕТ 2: тесты модулей (Gemini → одобрение → XML → Moodle)."""
        self._require_approver()
        from modules.rafail.quizzer import generate_quizzes
        from modules.rafail.connectors.moodle import MoodleConnector

        moodle = self.moodle or MoodleConnector()
        return await generate_quizzes(modules_content, self.approver, moodle)

    # ── AUTO-режим ────────────────────────────────────────────────────────────

    async def daily_collect(self) -> dict:
        """Ежедневный сбор материалов по всем источникам из БД."""
        from modules.rafail import collector
        return await collector.collect_all()

    async def sync_from_crm(self) -> str:
        """Кейсы из Kommo → материалы → case_study (черновики на одобрение)."""
        from modules.rafail import collector
        from modules.rafail import knowledge_base as kb

        added = await collector.collect_crm()
        if not added:
            return "✅ Рафаил выполнил\n📋 Задача: синхронизация CRM\n— новых сделок нет"
        # свежесобранные CRM-материалы → кейсы (черновики, ждут одобрения)
        mats = [m for m in kb.get_materials(domain="sales", limit=added)
                if m["source_type"] == "crm"]
        made = 0
        if self.approver is not None:
            from modules.rafail import processor
            for m in mats:
                try:
                    await processor.make_case_study(m["id"])
                    made += 1
                except Exception as e:  # noqa: BLE001
                    logger.error("[rafail] case_study #%d: %s", m["id"], e)
        return ("✅ Рафаил выполнил\n📋 Задача: синхронизация CRM\n"
                f"— новых сделок: {added}\n— кейсов подготовлено: {made} (ждут одобрения)")

    async def generate_progress_report(self) -> str:
        """Прогресс сотрудников из Moodle → текстовый отчёт владельцу."""
        from modules.rafail.connectors.moodle import MoodleConnector

        moodle = self.moodle or MoodleConnector()
        info = await moodle.ping()
        courses = await moodle.get_courses()
        users = await moodle.get_users()

        lines = [
            "📊 Отчёт по обучению — LK ENERGY ACADEMY",
            f"👥 Пользователей: {len(users)}",
            f"📚 Курсов: {len(courses)}",
            "",
        ]
        for c in courses[:10]:
            if c.get("id") == 1:  # сам сайт
                continue
            try:
                enrolled = await moodle.call(
                    "core_enrol_get_enrolled_users", courseid=c["id"]
                )
                lines.append(f"• {c.get('fullname', '?')}: записано {len(enrolled)}")
            except Exception:
                lines.append(f"• {c.get('fullname', '?')}: нет данных")
        return "\n".join(lines)

    async def answer_knowledge_query(self, query: str) -> str:
        """Поиск по rafail.db + краткий ответ Gemini на основе найденного."""
        if not query.strip():
            return "Укажите запрос для поиска"
        from modules.rafail import knowledge_base as kb

        hits = kb.search_materials(query, limit=5)
        if not hits:
            return f"🔍 По запросу «{query}» в базе знаний ничего не найдено"

        context = "\n---\n".join(
            f"[{h['title']}]\n{(h['raw_content'] or '')[:2000]}" for h in hits
        )
        from modules.rafail import processor
        try:
            answer = await processor._generate(
                f"Ответь кратко на русском на вопрос по материалам базы знаний "
                f"LK Energy Group.\n\nВопрос: {query}\n\nМатериалы:\n{context}"
            )
        except Exception as e:  # noqa: BLE001
            logger.error("[rafail] поиск: %s", e)
            titles = "\n".join(f"• {h['title']}" for h in hits)
            return f"🔍 Найдено {len(hits)} материалов (LLM недоступен):\n{titles}"
        return f"🔍 {answer}\n\nИсточники: {len(hits)} материалов БЗ"

    # ── форматирование отчётов (русский, по ТЗ) ──────────────────────────────

    @staticmethod
    def _fmt_collect(summary: dict) -> str:
        total = sum(summary.values())
        rows = "\n".join(f"• {name}: +{n}" for name, n in summary.items())
        return f"✅ Рафаил выполнил\n📋 Задача: сбор материалов\n{rows}\n— всего новых: {total}"

    @staticmethod
    def _fmt_fix(results: list[dict]) -> str:
        icons = {"uploaded": "✅", "approved": "✅", "rejected": "❌",
                 "timeout": "⏰", "not_found": "⚠️", "no_fixes": "➖", "error": "💥"}
        rows = "\n".join(
            f"{icons.get(r['status'], '•')} {r['module']}: {r['status']}" for r in results
        )
        return f"📋 Задача: слияние правок ++ (М1-М5)\n{rows}"
