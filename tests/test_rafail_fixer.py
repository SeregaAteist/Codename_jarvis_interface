"""RF-9: fixer — матчинг файлов модуля/++, полный цикл с моками Drive/LLM/approver."""

import asyncio

from modules.rafail.fixer import fix_module, match_module_files


def _fresh_db(tmp_path, monkeypatch):
    import modules.rafail.db as db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()
    return db


def test_match_module_files():
    files = [
        {"id": "a", "name": "М1. Ринок СЕС.docx"},
        {"id": "b", "name": "М1 ++ правки.docx"},
        {"id": "c", "name": "М10. Інше.docx"},  # не должен матчиться на М1
        {"id": "d", "name": "M2_module.md"},  # латиница
    ]
    mod, plus = match_module_files(files, "М1")
    assert mod["id"] == "a" and plus["id"] == "b"

    mod2, plus2 = match_module_files(files, "М2")
    assert mod2["id"] == "d" and plus2 is None


def test_fix_module_full_cycle(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb
    from modules.rafail import processor

    class FakeDrive:
        FOLDER_IDS = {"course_ses": "FOLDER"}
        uploaded = {}

        def folder(self, key):
            return self.FOLDER_IDS[key]

        async def list_folder(self, folder_id):
            return [
                {"id": "m1", "name": "М1. Ринок СЕС.docx"},
                {"id": "p1", "name": "М1 ++ доповнення.docx"},
            ]

        async def read_file(self, file_id):
            return "оригінал модуля" if file_id == "m1" else "правки ++"

        async def upload_file(self, content, filename, folder_id):
            self.uploaded.update(content=content, filename=filename)
            return {"id": "new_v2", "name": filename}

    async def fake_generate(prompt, quality=False):
        assert "оригінал модуля" in prompt and "правки ++" in prompt
        return "ЗЛИТА НОВА ВЕРСІЯ"

    monkeypatch.setattr(processor, "_generate", fake_generate)

    class AutoApprover:
        async def submit(self, pid, sources_count=1, timeout=None):
            kb.approve(pid)
            return "approved"

    drive = FakeDrive()
    res = asyncio.run(fix_module("М1", drive, AutoApprover()))

    assert res["status"] == "uploaded" and res["drive_file_id"] == "new_v2"
    assert drive.uploaded["content"] == "ЗЛИТА НОВА ВЕРСІЯ"
    assert "_v2_merged" in drive.uploaded["filename"]
    assert kb.get_processed(res["processed_id"])["status"] == "uploaded"
    assert kb.get_moodle_map(res["processed_id"])[0]["drive_file_id"] == "new_v2"


def test_fix_module_rejected_stops_upload(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import processor

    class FakeDrive:
        FOLDER_IDS = {"course_ses": "F"}

        def folder(self, key):
            return self.FOLDER_IDS[key]

        async def list_folder(self, folder_id):
            return [{"id": "m", "name": "М3 модуль"}, {"id": "p", "name": "М3 ++"}]

        async def read_file(self, file_id):
            return "x"

        async def upload_file(self, *a, **kw):
            raise AssertionError("upload не должен вызываться при reject")

    async def fake_generate(prompt, quality=False):
        return "merged"

    monkeypatch.setattr(processor, "_generate", fake_generate)

    class RejectApprover:
        async def submit(self, pid, sources_count=1, timeout=None):
            return "rejected"

    res = asyncio.run(fix_module("М3", FakeDrive(), RejectApprover()))
    assert res["status"] == "rejected"


def test_fix_module_missing_files(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)

    class EmptyDrive:
        FOLDER_IDS = {"course_ses": "F"}

        def folder(self, key):
            return self.FOLDER_IDS[key]

        async def list_folder(self, folder_id):
            return []

    res = asyncio.run(fix_module("М4", EmptyDrive(), None))
    assert res["status"] == "not_found"
