"""Уведомления (A-9): фильтр по вотчлисту, пустой вотчлист → всё."""

from agents.notify_agent import filter_by_watchlist, notify_new_episodes

from agents import db_agent as db

_ITEMS = [
    {"title": "Атака титанов", "url": "https://x/1", "episode": "5"},
    {"title": "Ван Пис", "url": "https://x/2", "episode": "1100"},
]


def test_empty_watchlist_passes_all(tmp_db):
    items, from_wl = filter_by_watchlist(_ITEMS)
    assert items == _ITEMS and from_wl is False


def test_filter_by_watchlist(tmp_db):
    db.add_to_watchlist("Атака титанов")
    items, from_wl = filter_by_watchlist(_ITEMS)
    assert from_wl is True
    assert [i["title"] for i in items] == ["Атака титанов"]


def test_dropped_not_notified(tmp_db):
    db.add_to_watchlist("Ван Пис")
    db.update_watchlist_status("Ван Пис", "dropped")
    items, from_wl = filter_by_watchlist(_ITEMS)
    assert items == _ITEMS and from_wl is False  # активных в вотчлисте нет → всё


async def test_notify_sends_filtered(tmp_db, sent_messages):
    db.add_to_watchlist("Атака титанов")
    await notify_new_episodes(_ITEMS)
    assert len(sent_messages) == 1
    assert "вотчлист" in sent_messages[0]
    assert "Атака титанов" in sent_messages[0]
    assert "Ван Пис" not in sent_messages[0]


async def test_notify_silent_when_no_match(tmp_db, sent_messages):
    db.add_to_watchlist("Наруто")
    await notify_new_episodes(_ITEMS)
    assert sent_messages == []


async def test_scan_complete_message(sent_messages):
    from agents.notify_agent import notify_scan_complete

    await notify_scan_complete(total=120, new_count=3)
    assert len(sent_messages) == 1 and "120" in sent_messages[0]
