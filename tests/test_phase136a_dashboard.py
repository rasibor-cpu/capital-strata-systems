from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


def test_phase136a_dashboard_renders_continuous_validation_section() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/mobile-dashboard")

    assert response.status_code == 200
    assert "Continuous Validation" in response.text
    assert "cv-status-badge" in response.text


def test_phase136a_runtime_artifact_freshness_api_safe() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/api/runtime-artifact-freshness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
