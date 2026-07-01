from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


def test_phase137a_dashboard_displays_publish_and_validation_times() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/mobile-dashboard")

    assert response.status_code == 200
    assert "Last Artifact Publish Time" in response.text
    assert "Last Validation Time" in response.text
    assert "cv-last-artifact-publish" in response.text
    assert "cv-last-validation" in response.text


def test_phase137a_runtime_validation_endpoints_remain_read_only_safe() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    for route in (
        "/api/runtime-health",
        "/api/runtime-artifact-freshness",
        "/api/validation-confidence",
        "/api/long-duration-validation",
    ):
        response = client.get(route)
        assert response.status_code == 200
        payload = response.json()
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False
