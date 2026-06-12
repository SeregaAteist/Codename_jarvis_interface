"""RF-10: questions_to_moodle_xml + quizzer pipeline (моки Moodle/LLM)."""
import asyncio

from modules.rafail.processor import questions_to_moodle_xml

_Q = [{
    "question": "Що таке СЕС?",
    "type": "multichoice",
    "answers": [
        {"text": "Сонячна електростанція", "correct": True, "feedback": "вірно"},
        {"text": "Система електронних сертифікатів", "correct": False},
    ],
}]


def test_moodle_xml_structure():
    xml = questions_to_moodle_xml(_Q, category="$course$/Рафаил/М1")
    assert xml.startswith('<?xml version="1.0"')
    assert '<question type="category">' in xml
    assert "$course$/Рафаил/М1" in xml
    assert '<question type="multichoice">' in xml
    assert 'fraction="100"' in xml and 'fraction="0"' in xml
    assert "<single>true</single>" in xml
    assert "вірно" in xml  # feedback сохранён


def test_moodle_xml_no_category():
    xml = questions_to_moodle_xml(_Q)
    assert '<question type="category">' not in xml


def test_quiz_pipeline_attach(tmp_path, monkeypatch):
    import modules.rafail.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()

    from modules.rafail import knowledge_base as kb
    from modules.rafail import processor, quizzer

    async def fake_generate(prompt, quality=False):
        return ('[{"question": "Q?", "type": "multichoice", "answers": ['
                '{"text": "A", "correct": true}, {"text": "B", "correct": false}]}]')
    monkeypatch.setattr(processor, "_generate", fake_generate)
    monkeypatch.setattr(quizzer, "quiz_map", lambda: {"М1": {"quiz_id": 42, "category_id": 7}})

    calls = {}

    class FakeMoodle:
        async def upload_quiz_xml(self, xml, filename=""):
            calls["xml"] = xml
            calls["filename"] = filename
            return 555

        async def add_random_questions(self, quiz_id, category_id, count=1, **kw):
            calls["attach"] = (quiz_id, category_id, count)

    class AutoApprover:
        async def submit(self, pid, sources_count=1, timeout=None):
            kb.approve(pid)
            return "approved"

    res = asyncio.run(quizzer.generate_quiz_for_module(
        "М1", "контент модуля", AutoApprover(), FakeMoodle()))

    assert res["status"] == "attached" and res["draft_itemid"] == 555
    assert calls["attach"] == (42, 7, 1)
    assert "Рафаил/М1" in calls["xml"]
    assert kb.get_processed(res["processed_id"])["status"] == "uploaded"


def test_quiz_pipeline_rejected(tmp_path, monkeypatch):
    import modules.rafail.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()

    from modules.rafail import processor, quizzer

    async def fake_generate(prompt, quality=False):
        return '[{"question": "Q?", "answers": [{"text": "A", "correct": true}]}]'
    monkeypatch.setattr(processor, "_generate", fake_generate)

    class RejectApprover:
        async def submit(self, pid, sources_count=1, timeout=None):
            return "rejected"

    class NoMoodle:
        async def upload_quiz_xml(self, *a, **kw):
            raise AssertionError("upload не должен вызываться при reject")

    res = asyncio.run(quizzer.generate_quiz_for_module(
        "М2", "контент", RejectApprover(), NoMoodle()))
    assert res["status"] == "rejected"
