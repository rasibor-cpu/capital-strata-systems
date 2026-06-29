from __future__ import annotations

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from launcher.css_launcher_config import LauncherConfig
from launcher.css_mobile_launcher import app


client = TestClient(app)


@pytest.fixture
def launcher_temp_dir():
    with tempfile.TemporaryDirectory() as td:
        original_artifacts = LauncherConfig.ARTIFACTS_DIR
        original_account = LauncherConfig.ACCOUNT_STATE_FILE
        original_session = LauncherConfig.SESSION_STATE_FILE
        original_ledger = LauncherConfig.CLOSED_TRADE_LEDGER_PATH
        original_supervisor = LauncherConfig.SUPERVISOR_STATE_FILE

        LauncherConfig.ARTIFACTS_DIR = os.path.join(td, "artifacts")
        LauncherConfig.ACCOUNT_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_account_state_pcnrass.json")
        LauncherConfig.SESSION_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_session_state_pcnrass.json")
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = os.path.join(td, "audit_logs", "closed_trades.jsonl")
        LauncherConfig.SUPERVISOR_STATE_FILE = os.path.join(td, "runtime", "supervisor", "css_runtime_supervisor_state.json")
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(LauncherConfig.CLOSED_TRADE_LEDGER_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)

        yield td

        LauncherConfig.ARTIFACTS_DIR = original_artifacts
        LauncherConfig.ACCOUNT_STATE_FILE = original_account
        LauncherConfig.SESSION_STATE_FILE = original_session
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = original_ledger
        LauncherConfig.SUPERVISOR_STATE_FILE = original_supervisor


def _write_quantitative_artifacts() -> None:
    with open(LauncherConfig.ACCOUNT_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "account_balance": 25000.0,
                "total_equity": 100000.0,
                "positions": [
                    {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 45000.0},
                    {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 30000.0},
                    {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 25000.0},
                ],
            },
            handle,
        )
    with open(LauncherConfig.SESSION_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"session": {"engine_mode": "PAPER", "market_regime": "TRENDING", "risk_status": "GREEN"}}, handle)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"status": "RUNNING", "last_heartbeat": "2026-06-29T00:00:00Z"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_policy_profile.json"), "w", encoding="utf-8") as handle:
        json.dump({"profile": "BALANCED"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json"), "w", encoding="utf-8") as handle:
        json.dump(
            [
                {"strategy_id": "trend", "asset_class": "equities", "symbol": "SPY", "realized_pnl": 120.0},
                {"strategy_id": "carry", "asset_class": "fx", "symbol": "EUR_USD", "realized_pnl": -20.0},
                {"strategy_id": "trend", "asset_class": "equities", "symbol": "QQQ", "realized_pnl": 90.0},
                {"strategy_id": "crypto", "asset_class": "crypto", "symbol": "BTC-USD", "realized_pnl": 45.0},
            ],
            handle,
        )


def test_quantitative_dashboard_api_routes_return_safe_responses(launcher_temp_dir) -> None:
    _write_quantitative_artifacts()

    routes = [
        "/api/quantitative-metrics",
        "/api/market-regime-intelligence",
        "/api/policy-profile",
        "/api/advisory-history",
        "/api/recommendation-tracker",
    ]
    payloads = []
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200
        payloads.append(response.json())

    assert payloads[0]["status"] == "OK"
    assert payloads[0]["advisory_only"] is True
    assert payloads[1]["detected_regime"] in {
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGING",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "CORRELATION_STRESS",
        "UNKNOWN",
    }
    assert payloads[2]["active_profile"] == "BALANCED"
    assert payloads[3]["advisory_only"] is True
    assert payloads[4]["advisory_only"] is True


def test_mobile_dashboard_contains_quantitative_learning_section(launcher_temp_dir) -> None:
    _write_quantitative_artifacts()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="quantitative-intelligence-card"' in html
    assert 'id="qi-detected-regime"' in html
    assert 'id="qi-rolling-sharpe"' in html
    assert 'id="qi-policy-profile"' in html
    assert 'id="qi-recommendation-tracker"' in html
    assert 'id="portfolio-intelligence-card"' in html
    assert 'id="adaptive-portfolio-card"' in html


def test_mobile_dashboard_quantitative_data_unavailable_fallback(launcher_temp_dir) -> None:
    response = client.get("/mobile")

    assert response.status_code == 200
    assert 'id="quantitative-intelligence-card"' in response.text
    assert 'id="quantitative-intelligence-unavailable"' in response.text
    assert "DATA UNAVAILABLE" in response.text


def test_quantitative_routes_do_not_create_trade_requests(launcher_temp_dir) -> None:
    _write_quantitative_artifacts()
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    client.get("/api/quantitative-metrics")
    client.get("/api/market-regime-intelligence")
    client.get("/api/policy-profile")
    client.get("/api/advisory-history")
    client.get("/api/recommendation-tracker")
    client.get("/mobile")

    assert not os.path.exists(trade_request_path)
