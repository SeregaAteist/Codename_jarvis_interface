"""RF-4..RF-8: notebooklm, sources+collector, processor (мок LLM), approver."""

import asyncio

import pytest


def _fresh_db(tmp_path, monkeypatch):
    import modules.rafail.db as db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()
    return db


# ── RF-4: NotebookLM ──────────────────────────────────────────────────────────


def test_notebooklm_push_builds_filename(monkeypatch):
    from modules.rafail.connectors.notebooklm import NotebookLMConnector

    captured = {}

    class FakeDrive:
        async def upload_file(self, content, filename, folder_id):
            captured.update(content=content, filename=filename, folder=folder_id)
            return {"id": "f1", "name": filename}

    nb = NotebookLMConnector(drive=FakeDrive())
    nb.folders["ses"] = "FOLDER_SES"
    asyncio.run(nb.push("ses", "Інвертори: вибір/налаштування", "text"))
    assert captured["folder"] == "FOLDER_SES"
    assert captured["filename"].endswith(".md")
    assert "/" not in captured["filename"].split("_", 1)[1]  # спецсимволы вычищены


def test_notebooklm_fails_without_folder():
    from modules.rafail.connectors.notebooklm import NotebookLMConnector

    nb = NotebookLMConnector(drive=object())
    nb.folders = {"ses": "", "sales": "", "energy": ""}
    with pytest.raises(RuntimeError, match="NOTEBOOKLM"):
        asyncio.run(nb.push("ses", "t", "c"))


# ── RF-5: sources + collector ─────────────────────────────────────────────────


def test_load_sources_all_domains(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)  # seed заполняет таблицу sources
    from modules.rafail import collector

    sources = collector.load_sources()
    domains = {s["domain"] for s in sources}
    assert {"ses", "energy", "sales"} <= domains
    assert all(s.get("url") and s.get("type") in ("rss", "web") for s in sources)
    assert collector.load_sources("sales")  # фильтр по домену работает


def test_collect_rss_dedup(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from core.parsers.rss import RssParser
    from modules.rafail import collector
    from modules.rafail import knowledge_base as kb

    posts = [
        {
            "title": "Нові тарифи НКРЕКП",
            "url": "https://x/1",
            "published": None,
            "source": "s",
        },
        {"title": "Без URL — пропуск", "url": "", "published": None, "source": "s"},
    ]

    async def fake_fetch(self, url, hours=48, limit=10, source=""):
        return posts

    monkeypatch.setattr(RssParser, "fetch", fake_fetch)

    src = {
        "name": "T",
        "url": "https://x/feed",
        "type": "rss",
        "track": "all",
        "domain": "energy",
    }
    assert asyncio.run(collector.collect_rss(src)) == 1
    # повторный сбор — дедуп по URL
    assert asyncio.run(collector.collect_rss(src)) == 0
    assert kb.get_stats()["materials"] == 1


def test_parse_rss2_format():
    from core.parsers.rss import parse_feed

    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>СЕС новина</title><link>https://x/a</link>
      <pubDate>Mon, 09 Jun 2026 10:00:00 +0200</pubDate></item>
    </channel></rss>"""
    posts = parse_feed(xml, "src", limit=5, hours=None)
    assert len(posts) == 1 and posts[0]["title"] == "СЕС новина"


# ── RF-7: processor (мок Gemini) ─────────────────────────────────────────────


def test_make_summary_and_section(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb
    from modules.rafail import processor

    async def fake_generate(prompt, quality=False):
        return "## Згенерований контент\n— теза"

    monkeypatch.setattr(processor, "_generate", fake_generate)

    mid = kb.add_material(
        domain="ses", track="sales", title="Інвертори", raw_content="дані"
    )
    pid = asyncio.run(processor.make_summary(mid))
    assert kb.get_processed(pid)["content_type"] == "summary"

    pid2 = asyncio.run(processor.make_course_section(mid))
    row = kb.get_processed(pid2)
    assert row["content_type"] == "course_section" and row["status"] == "pending"


def test_make_quiz_validates_json(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import processor

    good = """```json
    [{"question": "Що таке СЕС?", "type": "multichoice", "answers": [
      {"text": "Сонячна електростанція", "correct": true, "feedback": "так"},
      {"text": "Ні", "correct": false}]}]
    ```"""

    async def fake_generate(prompt, quality=False):
        return good

    monkeypatch.setattr(processor, "_generate", fake_generate)

    pid = asyncio.run(processor.make_quiz("контент модуля", "М1", "sales"))
    from modules.rafail import knowledge_base as kb

    assert '"question"' in kb.get_processed(pid)["content"]


def test_parse_quiz_json_rejects_bad():
    from modules.rafail.processor import parse_quiz_json

    with pytest.raises(ValueError):
        parse_quiz_json("нет json")
    with pytest.raises(ValueError):  # два правильных ответа
        parse_quiz_json(
            '[{"question":"q","answers":[{"text":"a","correct":true},{"text":"b","correct":true}]}]'
        )


# ── RF-8: approver ────────────────────────────────────────────────────────────


def test_approver_approve_flow(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb
    from modules.rafail.approver import RafailApprover

    mid = kb.add_material(domain="ses", track="sales", title="m", raw_content="c")
    pid = kb.add_processed(mid, "course_section", "sales", "Секція", "## Контент")

    sent = {}

    async def send(msg, key, processed_id):
        sent["key"] = key
        assert "Рафаил подготовил материал" in msg
        assert "ses" in msg

    async def run():
        ap = RafailApprover(send)
        task = asyncio.create_task(ap.submit(pid, timeout=5))
        await asyncio.sleep(0.05)  # дать submit отправить план
        assert ap.resolve(sent["key"], "approve")
        return await task

    assert asyncio.run(run()) == "approved"
    assert kb.get_processed(pid)["status"] == "approved"


def test_approver_reject_with_reason(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb
    from modules.rafail.approver import RafailApprover

    pid = kb.add_processed(None, "quiz", "all", "Тест", "[]")
    sent = {}

    async def send(msg, key, processed_id):
        sent["key"] = key

    async def run():
        ap = RafailApprover(send)
        task = asyncio.create_task(ap.submit(pid, timeout=5))
        await asyncio.sleep(0.05)
        ap.resolve(sent["key"], "reject:не той стиль")
        return await task

    assert asyncio.run(run()) == "rejected"
    row = kb.get_processed(pid)
    assert row["status"] == "rejected" and row["rejection_reason"] == "не той стиль"
