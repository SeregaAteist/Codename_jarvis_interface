"""RF-8/RF-9: uploader — структура курсов и заливка одобренных секций."""
import asyncio

from modules.rafail import knowledge_base as kb
from modules.rafail.uploader import create_course_structure, upload_to_moodle


def _fresh_db(tmp_path, monkeypatch):
    import modules.rafail.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()
    return db


class FakeMoodle:
    def __init__(self):
        self.categories: list[dict] = []
        self.courses: list[dict] = []

    async def get_categories(self):
        return self.categories

    async def create_category(self, name, parent_id=0):
        cat = {"id": len(self.categories) + 100, "name": name}
        self.categories.append(cat)
        return cat

    async def create_course(self, title, category_id, description="",
                            shortname="", summary_format=1):
        course = {"id": len(self.courses) + 500,
                  "shortname": shortname or title,
                  "summaryformat": summary_format}
        self.courses.append(course)
        return course


def test_create_structure_idempotent(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    m = FakeMoodle()
    first = asyncio.run(create_course_structure("sales", "trainee", m))
    second = asyncio.run(create_course_structure("sales", "trainee", m))
    assert first == second
    assert len(m.courses) == 1  # повторный вызов не создаёт дублей


def test_upload_to_moodle_marks_and_maps(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    pid = kb.add_processed(None, "universal_section", "trainee",
                           "Тест-секция", "# Контент")
    m = FakeMoodle()
    res = asyncio.run(upload_to_moodle(pid, m))
    assert res["already"] is False and res["course_id"]
    assert kb.get_processed(pid)["status"] == "uploaded"
    assert kb.get_moodle_map(pid)[0]["moodle_course_id"] == res["course_id"]
    # контент уходит как Markdown summary
    assert m.courses[-1]["summaryformat"] == 4

    again = asyncio.run(upload_to_moodle(pid, m))
    assert again["already"] is True
    assert len([c for c in m.courses if c["id"] == res["course_id"]]) == 1
