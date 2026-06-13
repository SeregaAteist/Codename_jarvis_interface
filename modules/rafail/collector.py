"""Collector — сбор материалов из всех источников (RF-5/RF-6).

RF-5: RSS + web (таблица sources в rafail.db) → materials с дедупом по URL.
RF-6: Drive (модули курса), CRM (Kommo), Ringostat — отдельные collect_*-методы;
      активируются когда появятся токены в .env (KOMMO_*, RINGOSTAT_*).
"""

from __future__ import annotations

import logging
from typing import Any

from core.parsers.html import HtmlParser
from core.parsers.rss import RssParser
from modules.rafail import knowledge_base as kb
from shared.config.secrets import opt

logger = logging.getLogger(__name__)


class RafailCollector:
    """Сборщик материалов из RSS, web, Drive, CRM и Ringostat."""

    def __init__(self) -> None:
        self._rss: RssParser | None = None
        self._html: HtmlParser | None = None

    @property
    def rss_parser(self) -> RssParser:
        if self._rss is None:
            self._rss = RssParser()
        return self._rss

    @property
    def html_parser(self) -> HtmlParser:
        if self._html is None:
            self._html = HtmlParser()
        return self._html

    def load_sources(self, domain: str = "") -> list[dict[str, Any]]:
        """Активные источники из БД (управление — TG-кнопками)."""
        return kb.get_sources(domain=domain, enabled_only=True)

    # ── RSS / web (RF-5) ──────────────────────────────────────────────────────

    async def collect_rss(
        self,
        source: dict[str, Any],
        hours: int | None = 48,
        limit: int = 10,
    ) -> int:
        """Лента источника → materials. Возвращает число новых записей."""
        posts = await self.rss_parser.fetch(
            source["url"], hours=hours, limit=limit, source=source["name"]
        )
        added = 0
        for p in posts:
            if not p["url"] or kb.material_exists(p["url"]):
                continue
            kb.add_material(
                domain=source["domain"],
                track=source.get("track", "all"),
                title=p["title"],
                raw_content=p.get("body") or p["title"],
                source_url=p["url"],
                source_type="rss",
            )
            added += 1
        return added

    async def collect_web(self, source: dict[str, Any], limit: int = 10) -> int:
        """Скрейп списка ссылок по selector → materials (заголовок+URL)."""
        try:
            items = await self.html_parser.fetch(
                source["url"], selector=source.get("selector")
            )
        except Exception as e:
            logger.warning("[collector] %s недоступен: %s", source["name"], e)
            return 0
        if not isinstance(items, list):
            return 0
        added = 0
        for el in items[:limit]:
            title = el.get("text", "").strip()
            if not title:
                continue
            pseudo_url = f"{source['url']}#{title[:60]}"
            if kb.material_exists(pseudo_url):
                continue
            kb.add_material(
                domain=source["domain"],
                track=source.get("track", "all"),
                title=title,
                raw_content=el.get("html", title),
                source_url=pseudo_url,
                source_type="web",
            )
            added += 1
        return added

    async def collect_all(
        self, domain: str = "", hours: int | None = 48
    ) -> dict[str, int]:
        """Обойти все источники домена (или все). Возвращает сводку по источникам."""
        summary: dict[str, int] = {}
        for src in self.load_sources(domain):
            try:
                if src.get("type") == "rss":
                    n = await self.collect_rss(src, hours=hours)
                elif src.get("type") == "web":
                    n = await self.collect_web(src)
                else:
                    continue
            except Exception as e:
                logger.error("[collector] %s: %s", src["name"], e)
                n = 0
            summary[src["name"]] = n
        if not opt("GOOGLE_SA_JSON"):
            logger.info("[collector] GOOGLE_SA_JSON не задан — Drive пропущен")
        else:
            try:
                summary["drive:course_ses"] = await self.collect_drive("course_ses")
            except Exception as e:
                logger.error("[collector] drive: %s", e)
        total = sum(summary.values())
        kb.log_sync("collect", "ok", f"domain={domain or 'all'} added={total}")
        logger.info("[collector] собрано %d новых материалов: %s", total, summary)
        cleaned = self.cleanup_materials(days=7)
        if cleaned:
            logger.info("[collector] очищено %d устаревших материалов", cleaned)
        return summary

    def cleanup_materials(self, days: int = 7) -> int:
        """RF-5.2: materials — временный буфер. Удалить обработанные и старые."""
        from modules.rafail import db

        with db.connect() as c:
            deleted = c.execute("""
                DELETE FROM materials WHERE id IN (
                    SELECT DISTINCT material_id FROM processed WHERE material_id IS NOT NULL
                )
            """).rowcount
            deleted += c.execute(
                "DELETE FROM materials WHERE collected_at < datetime('now', ?)",
                (f"-{days} days",),
            ).rowcount
        return deleted

    # ── Drive (RF-6) ──────────────────────────────────────────────────────────

    async def collect_drive(
        self,
        folder_key: str,
        domain: str = "internal",
        track: str = "all",
    ) -> int:
        """Файлы Drive-папки (по ключу из FOLDER_IDS) → materials."""
        from modules.rafail.connectors.drive import DriveConnector

        drive = DriveConnector()
        folder_id = drive.FOLDER_IDS[folder_key]
        files = await drive.list_folder(folder_id)
        added = 0
        for f in files:
            url = f"drive://{f['id']}"
            if kb.material_exists(url):
                continue
            try:
                content = await drive.read_file(f["id"])
            except Exception as e:
                logger.warning("[collector] drive %s: %s", f["name"], e)
                continue
            kb.add_material(
                domain=domain,
                track=track,
                title=f["name"],
                raw_content=content,
                source_url=url,
                source_type="drive",
            )
            added += 1
        kb.log_sync("collect_drive", "ok", f"{folder_key} added={added}")
        return added

    # ── CRM / Ringostat (RF-6, активируются при наличии токенов) ─────────────

    async def collect_crm(self, limit: int = 20) -> int:
        """Успешные сделки из Kommo → materials (для case_study)."""
        if not opt("KOMMO_TOKEN"):
            logger.info("[collector] KOMMO_TOKEN не задан — пропуск CRM")
            return 0
        from modules.rafail.connectors.kommo import KommoConnector

        deals = await KommoConnector().get_won_deals(limit=limit)
        added = 0
        for d in deals:
            url = f"kommo://lead/{d['id']}"
            if kb.material_exists(url):
                continue
            kb.add_material(
                domain="sales",
                track="sales",
                title=d.get("name", f"Сделка {d['id']}"),
                raw_content=str(d),
                source_url=url,
                source_type="crm",
            )
            added += 1
        return added

    async def collect_ringostat(self, limit: int = 20) -> int:
        """Транскрипты звонков Ringostat → materials (для case_study)."""
        if not opt("RINGOSTAT_TOKEN"):
            logger.info("[collector] RINGOSTAT_TOKEN не задан — пропуск Ringostat")
            return 0
        from modules.rafail.connectors.ringostat import RingostatConnector

        calls = await RingostatConnector().get_transcripts(limit=limit)
        added = 0
        for call in calls:
            url = f"ringostat://call/{call['id']}"
            if kb.material_exists(url):
                continue
            kb.add_material(
                domain="sales",
                track="sales",
                title=call.get("title", f"Звонок {call['id']}"),
                raw_content=call.get("transcript", ""),
                source_url=url,
                source_type="ringostat",
            )
            added += 1
        return added


# синглтон
_collector: RafailCollector | None = None


def _get_collector() -> RafailCollector:
    global _collector
    if _collector is None:
        _collector = RafailCollector()
    return _collector


# backward compat — модульные функции
def load_sources(domain: str = "") -> list[dict[str, Any]]:
    return _get_collector().load_sources(domain)


async def collect_rss(
    source: dict[str, Any], hours: int | None = 48, limit: int = 10
) -> int:
    return await _get_collector().collect_rss(source, hours=hours, limit=limit)


async def collect_web(source: dict[str, Any], limit: int = 10) -> int:
    return await _get_collector().collect_web(source, limit=limit)


async def collect_all(domain: str = "", hours: int | None = 48) -> dict[str, int]:
    return await _get_collector().collect_all(domain=domain, hours=hours)


def cleanup_materials(days: int = 7) -> int:
    return _get_collector().cleanup_materials(days=days)


async def collect_drive(
    folder_key: str, domain: str = "internal", track: str = "all"
) -> int:
    return await _get_collector().collect_drive(folder_key, domain=domain, track=track)


async def collect_crm(limit: int = 20) -> int:
    return await _get_collector().collect_crm(limit=limit)


async def collect_ringostat(limit: int = 20) -> int:
    return await _get_collector().collect_ringostat(limit=limit)
