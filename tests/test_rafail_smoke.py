"""RF-14: smoke полного цикла Рафаила — меню, сбор, статус, scheduler-джобы."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "modules" / "tg-media-analyzer"))


def _fresh_db(tmp_path, monkeypatch):
    import modules.rafail.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()


def test_menus_build():
    """Меню Рафаила и Аниме собираются, кнопки на русском."""
    from bot.rafail_menu import main_menu, settings_menu, approval_keyboard
    from bot.anime_menu import main_menu as anime_main

    rf = main_menu().inline_keyboard
    texts = [b.text for row in rf for b in row]
    assert "📊 Статус" in texts and "⚙️ Настройки" in texts

    st = settings_menu().inline_keyboard
    assert any("Источники" in b.text for row in st for b in row)

    ap = approval_keyboard("k").inline_keyboard
    ap_texts = [b.text for row in ap for b in row]
    assert "✅ Залить" in ap_texts and "📝 Правки" in ap_texts

    an = anime_main().inline_keyboard
    an_texts = [b.text for row in an for b in row]
    assert "📋 Список" in an_texts and "🎯 Рекомендации" in an_texts


def test_smoke_status_and_collect(tmp_path, monkeypatch):
    """Статус БЗ отвечает; сбор по моковому RSS проходит без падений."""
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb
    from agents.rafail import RafailAgent
    from core.parsers.rss import RssParser

    s = kb.get_stats()
    assert s["materials"] == 0

    async def fake_fetch(self, url, hours=48, limit=10, source=""):
        return [{"title": "Тест", "url": f"https://x/{source}", "published": None,
                 "source": source}]
    monkeypatch.setattr(RssParser, "fetch", fake_fetch)

    from core.parsers.html import HtmlParser

    async def fake_html(self, url, selector=None):
        return []
    monkeypatch.setattr(HtmlParser, "fetch", fake_html)

    out = asyncio.run(RafailAgent().execute("collect"))
    assert "✅ Рафаил выполнил" in out
    assert kb.get_stats()["materials"] > 0


def test_scheduler_jobs_registered(monkeypatch):
    """RF-13: все джобы регистрируются с валидным cron."""
    import core.scheduler as cs

    scheduled = {}

    class FakeDriver:
        def schedule(self, job_id, cron, cb):
            scheduled[job_id] = cron
        def start(self):
            pass
        def remove(self, job_id):
            pass
        def list_jobs(self):
            return list(scheduled)

    monkeypatch.setattr(cs, "scheduler", FakeDriver())
    cs.register_default_jobs()
    assert scheduled["rafail_collect"] == "0 8 * * *"
    assert scheduled["rafail_report"] == "0 9 * * 1"
    assert scheduled["anime_check"] == "0 */3 * * *"
