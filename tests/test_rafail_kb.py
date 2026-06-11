"""RF-1: rafail.db + knowledge_base — init, CRUD, статусы, лог."""


def _fresh_db(tmp_path, monkeypatch):
    import modules.rafail.db as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "rafail.db")
    db.init_db()
    return db


def test_init_db(tmp_path, monkeypatch):
    db = _fresh_db(tmp_path, monkeypatch)
    with db.connect() as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"materials", "processed", "moodle_map", "sync_log"} <= tables


def test_materials_crud(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb

    mid = kb.add_material(
        domain="ses", track="sales", title="Воронка продажів СЕС",
        raw_content="контент", source_url="https://example.com/a", source_type="web",
    )
    assert mid == 1
    assert kb.get_material(mid)["title"] == "Воронка продажів СЕС"
    assert kb.material_exists("https://example.com/a")
    assert not kb.material_exists("https://example.com/other")

    # track-фильтр включает 'all'
    kb.add_material(domain="ses", track="all", title="Загальний", raw_content="x")
    assert len(kb.get_materials(domain="ses", track="sales")) == 2
    assert kb.search_materials("Воронка")[0]["id"] == mid


def test_processed_lifecycle(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb

    mid = kb.add_material(domain="ses", track="sales", title="m", raw_content="c")
    pid = kb.add_processed(mid, "course_section", "sales", "Секція 1", "текст")

    assert kb.get_processed(pid)["status"] == "pending"
    assert len(kb.get_pending()) == 1

    kb.approve(pid)
    assert kb.get_processed(pid)["status"] == "approved"
    assert kb.get_processed(pid)["approved_at"] is not None

    kb.update_content(pid, "новий текст")
    row = kb.get_processed(pid)
    assert row["status"] == "pending" and row["content"] == "новий текст"

    kb.reject(pid, "не той стиль")
    row = kb.get_processed(pid)
    assert row["status"] == "rejected" and row["rejection_reason"] == "не той стиль"

    kb.mark_uploaded(pid)
    assert kb.get_processed(pid)["status"] == "uploaded"


def test_moodle_map_and_log(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb

    pid = kb.add_processed(None, "quiz", "sales", "Тест М1", "[]")
    kb.map_moodle(pid, moodle_course_id=2, moodle_section_id=5, drive_file_id="abc")
    entries = kb.get_moodle_map(pid)
    assert len(entries) == 1 and entries[0]["moodle_course_id"] == 2

    kb.log_sync("upload", "ok", "М1 → Moodle")
    log = kb.get_sync_log()
    assert log[0]["action"] == "upload" and log[0]["status"] == "ok"


def test_stats(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    from modules.rafail import knowledge_base as kb

    kb.add_material(domain="ses", track="all", title="m", raw_content="c")
    p1 = kb.add_processed(1, "quiz", "all", "t", "c")
    kb.add_processed(1, "summary", "all", "t2", "c2")
    kb.approve(p1)

    s = kb.get_stats()
    assert s["materials"] == 1 and s["approved"] == 1 and s["pending"] == 1
