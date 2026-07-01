from fastapi.testclient import TestClient

from launcher.css_mobile_launcher import app


def test_regime_aware_weighting_endpoint_returns_safe_json() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/api/regime-aware-weighting")

    assert response.status_code == 200
    payload = response.json()
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert payload["weight_sum"] == 100.0
    assert set(payload["weights"]) == {"technical", "fundamental", "sentiment", "quantitative"}


def test_multi_factor_endpoint_includes_regime_weighting_metadata() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/api/multi-factor-signal")

    assert response.status_code == 200
    payload = response.json()
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert "regime_weights" in payload
    assert "weighting_confidence_adjustment" in payload
    assert "weighting_reasons" in payload


def test_phase138b_dashboard_renders_weighting_rows_safely() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/mobile-dashboard")

    assert response.status_code == 200
    assert "mi-regime-weights" in response.text
    assert "mi-weighting-reasons" in response.text
    assert "mi-confidence-adjustment" in response.text
    assert "DATA UNAVAILABLE" in response.text
