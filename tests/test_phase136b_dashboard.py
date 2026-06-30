from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


def test_phase136b_apis_return_safe_json() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    for route in (
        "/api/runtime-validation-monitor",
        "/api/runtime-validation-metrics",
        "/api/runtime-health-trend",
        "/api/validation-confidence",
        "/api/long-duration-validation",
    ):
        response = client.get(route)
        assert response.status_code == 200
        payload = response.json()
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False


def test_phase136b_dashboard_has_data_unavailable_fallbacks() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/mobile-dashboard")

    assert response.status_code == 200
    assert "DATA UNAVAILABLE" in response.text
    assert "Long Duration Samples" in response.text
