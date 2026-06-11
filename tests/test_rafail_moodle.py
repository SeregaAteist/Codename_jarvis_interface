"""RF-2: MoodleConnector — ping, обработка ошибок, сериализация (мок, без сети)."""
import asyncio

import pytest

from modules.rafail.connectors.moodle import MoodleConnector, MoodleError, _flatten


def _conn() -> MoodleConnector:
    return MoodleConnector(url="https://moodle.test", token="tok")


def test_endpoint():
    assert _conn().endpoint == "https://moodle.test/webservice/rest/server.php"


def test_flatten_moodle_style():
    flat = _flatten({"courses": [{"fullname": "X", "categoryid": 2}], "id": 7})
    assert flat == {"courses[0][fullname]": "X", "courses[0][categoryid]": 2, "id": 7}


def test_ping_parses_site_info(monkeypatch):
    async def fake_call(self, wsfunction, **params):
        assert wsfunction == "core_webservice_get_site_info"
        return {
            "sitename": "LK ENERGY ACADEMY", "username": "sergey",
            "userid": 171, "release": "4.5.1+", "functions": [{"name": "f1"}, {"name": "f2"}],
        }
    monkeypatch.setattr(MoodleConnector, "call", fake_call)
    info = asyncio.run(_conn().ping())
    assert info["sitename"] == "LK ENERGY ACADEMY"
    assert info["functions_count"] == 2


def test_moodle_error_raised(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"exception": "moodle_exception", "errorcode": "invalidtoken",
                    "message": "Недійсний токен"}

    class FakeClient:
        def __init__(self, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            pass
        async def post(self, url, data=None):
            return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    with pytest.raises(MoodleError) as e:
        asyncio.run(_conn().call("any_function"))
    assert e.value.errorcode == "invalidtoken"
