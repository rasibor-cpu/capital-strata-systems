from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


def test_phase139a_learning_apis_return_read_only_payloads() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    for route in (
        "/api/factor-performance",
        "/api/factor-attribution",
        "/api/rolling-reliability",
        "/api/regime-learning",
        "/api/adaptive-weight-recommendations",
        "/api/confidence-calibration-learning",
        "/api/engine-health-learning",
    ):
        response = client.get(route)
        assert response.status_code == 200
        payload = response.json()
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False


def test_phase139a_dashboard_renders_learning_optimization_section() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/mobile-dashboard")

    assert response.status_code == 200
    assert "Learning & Optimization" in response.text
    assert "lo-factor-performance-status" in response.text
    assert "DATA UNAVAILABLE" in response.text
