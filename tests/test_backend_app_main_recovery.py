from __future__ import annotations

import os

os.environ.setdefault("CSS_HOST_SECURITY_PROFILE", "open_dev")

from fastapi.testclient import TestClient

from backend.app.main import HeadlessRunRequest, _build_headless_config, app
from backend.monitoring.css_alert_repository import CSSAlertRepository


client = TestClient(app)


def test_main_app_exposes_required_routes() -> None:
    routes = {(route.path, method) for route in app.routes for method in route.methods}
    assert ("/health", "GET") in routes
    assert ("/alerts", "GET") in routes
    assert ("/engine/headless/run", "POST") in routes


def test_health_endpoint_is_stable_and_read_only() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "time_utc" in payload
    assert isinstance(payload["auth_loaded"], bool)
    assert isinstance(payload["headless_loaded"], bool)


def test_alerts_endpoint_uses_passive_repository(monkeypatch) -> None:
    monkeypatch.setattr(
        CSSAlertRepository,
        "list_alerts",
        lambda self, limit=50: [{"alert_id": "test", "limit": limit}],
    )
    response = client.get("/alerts?limit=7")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["alerts"] == [{"alert_id": "test", "limit": 7}]


def test_headless_request_validation_remains_bounded() -> None:
    assert client.post("/engine/headless/run", json={"steps": 0}).status_code == 422
    assert client.post("/engine/headless/run", json={"steps": 501}).status_code == 422
    request = HeadlessRunRequest()
    assert request.execution_mode == "SIMULATION"


def test_headless_config_remains_fail_closed() -> None:
    config, error = _build_headless_config()
    assert error is None
    assert config is not None
    for attribute in ("execution_locked", "locked", "lock_execution"):
        if hasattr(config, attribute):
            assert getattr(config, attribute) is True
    if hasattr(config, "live_execution"):
        assert config.live_execution is False
