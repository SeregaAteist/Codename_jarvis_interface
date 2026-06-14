from unittest.mock import patch

import pytest


@pytest.fixture
def browser():
    with patch.dict(
        "os.environ",
        {
            "MOODLE_URL": "https://test.moodle.com",
            "MOODLE_ADMIN_USER": "admin",
            "MOODLE_ADMIN_PASS": "test",
        },
    ):
        from modules.rafail.connectors.moodle_browser import MoodleBrowser

        return MoodleBrowser()


def test_moodle_browser_init(browser):
    assert browser._url == "https://test.moodle.com"
    assert browser._user == "admin"


def test_get_moodle_browser_singleton():
    import modules.rafail.connectors.moodle_browser as mod

    mod._browser = None  # reset between test runs
    from modules.rafail.connectors.moodle_browser import get_moodle_browser

    b1 = get_moodle_browser()
    b2 = get_moodle_browser()
    assert b1 is b2
