from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


def test_phase138a_dashboard_renders_market_intelligence_section() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/mobile-dashboard")

    assert response.status_code == 200
    assert "Market Intelligence" in response.text
    assert "mi-technical-signal" in response.text
    assert "DATA UNAVAILABLE" in response.text


def test_phase138a_market_intelligence_endpoints_safe() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    for route in (
        "/api/technical-analysis",
        "/api/fundamental-analysis",
        "/api/sentiment-intelligence",
        "/api/quantitative-alpha",
        "/api/multi-factor-signal",
    ):
        response = client.get(route)
        assert response.status_code == 200
        payload = response.json()
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False
