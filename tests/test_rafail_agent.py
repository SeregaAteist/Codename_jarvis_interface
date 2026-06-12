"""RF-11: RafailAgent — execute-роутинг, AUTO/APPROVE, форматирование отчётов."""
import asyncio

import pytest

from agents.rafail import RafailAgent


def _fresh_db(tmp_path, monkeypatch):
    import modules.rafail.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()


def test_capabilities_present():
    a = RafailAgent()
    assert {"module_fix", "quiz_create", "knowledge_search",
            "progress_report", "knowledge_collect"} <= set(a.capabilities)


def test_approve_ops_require_approver():
    a = RafailAgent()
    with pytest.raises(RuntimeError, match="approver"):
        asyncio.run(a.fix_pending_modules())
    with pytest.raises(RuntimeError, match="approver"):
        asyncio.run(a.generate_quizzes({"М1": "x"}))


def test_execute_routes_collect(monkeypatch):
    a = RafailAgent()

    async def fake_collect():
        return {"Ecotown": 3, "PV Magazine": 1}
    monkeypatch.setattr(a, "daily_collect", fake_collect)

    out = asyncio.run(a.execute("collect"))
    assert "✅ Рафаил выполнил" in out and "всего новых: 4" in out


def test_execute_routes_search(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb
    from modules.rafail import processor

    kb.add_material(domain="ses", track="all", title="Інвертори Huawei",
                    raw_content="технічні дані інверторів")

    async def fake_generate(prompt, quality=False):
        assert "Інвертори" in prompt
        return "Ответ по инверторам"
    monkeypatch.setattr(processor, "_generate", fake_generate)

    out = asyncio.run(a_search("search Інвертори"))
    assert "Ответ по инверторам" in out


def a_search(cmd):
    return RafailAgent().execute(cmd)


def test_search_empty_db(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    out = asyncio.run(RafailAgent().answer_knowledge_query("чого нема"))
    assert "ничего не найдено" in out


def test_fmt_fix_report():
    out = RafailAgent._fmt_fix([
        {"module": "М1", "status": "uploaded"},
        {"module": "М2", "status": "no_fixes"},
        {"module": "М3", "status": "error", "error": "x"},
    ])
    assert "✅ М1" in out and "➖ М2" in out and "💥 М3" in out
