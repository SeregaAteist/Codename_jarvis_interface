"""RF-3: DriveConnector — FOLDER_IDS, fail-fast без кредов, операции (мок)."""
import asyncio

import pytest

from modules.rafail.connectors.drive import DriveConnector


def test_folder_ids_complete():
    ids = DriveConnector.FOLDER_IDS
    required = {
        "moodle_root", "course_ses", "section_start", "section_market",
        "section_ses", "section_equip", "section_client", "section_funnel",
        "section_finance", "section_crm", "section_epc", "section_after",
        "kb_v2", "template",
    }
    assert required <= set(ids)
    assert all(v for v in ids.values())


def test_fail_fast_without_credentials():
    d = DriveConnector(sa_json="/nonexistent/sa.json")
    assert not d.is_configured()
    with pytest.raises(RuntimeError, match="GOOGLE_SA_JSON"):
        d._service()


def test_read_kb_v2_uses_folder_id(monkeypatch):
    d = DriveConnector(sa_json="")
    captured = {}

    async def fake_read(file_id):
        captured["id"] = file_id
        return "KB content"

    monkeypatch.setattr(d, "read_file", fake_read)
    out = asyncio.run(d.read_kb_v2())
    assert out == "KB content"
    assert captured["id"] == DriveConnector.FOLDER_IDS["kb_v2"]


def test_list_folder_pagination(monkeypatch):
    d = DriveConnector(sa_json="")

    class FakeFiles:
        def __init__(self):
            self.calls = 0
        def list(self, **kw):
            self.calls += 1
            page = self.calls
            class R:
                def execute(s):
                    if page == 1:
                        return {"files": [{"id": "a", "name": "f1"}], "nextPageToken": "t"}
                    return {"files": [{"id": "b", "name": "f2"}]}
            return R()

    class FakeSvc:
        def __init__(self):
            self._files = FakeFiles()
        def files(self):
            return self._files

    monkeypatch.setattr(d, "_service", lambda: FakeSvc())
    files = asyncio.run(d.list_folder("folder123"))
    assert [f["name"] for f in files] == ["f1", "f2"]
