"""Integration tests for core API endpoints (FastAPI only).

Skipped automatically when core.main does not expose a FastAPI `app`
(currently uses http.server; tests activate once FastAPI is wired up).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.expanduser("~/Projects/jarvis"))

pytest.importorskip("fastapi", reason="fastapi not installed")

try:
    from core.main import app as _app  # noqa: F401
except (ImportError, AttributeError):
    pytest.skip("core.main has no FastAPI app", allow_module_level=True)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from core.main import app

    return TestClient(app)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_agents_status_endpoint(client):
    r = client.get("/api/agents/status")
    assert r.status_code == 200
    assert "services" in r.json()


def test_rafail_status_endpoint(client):
    r = client.get("/api/rafail/status")
    assert r.status_code == 200


def test_metrics_endpoint(client):
    r = client.get("/api/metrics")
    assert r.status_code in (200, 404)
