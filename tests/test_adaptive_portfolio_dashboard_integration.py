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


def _write_phase130_artifacts() -> None:
    with open(LauncherConfig.ACCOUNT_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "account_balance": 25000.0,
                "total_equity": 100000.0,
                "buying_power": 50000.0,
                "positions": [
                    {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 40000.0},
                    {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 35000.0},
                    {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 25000.0},
                ],
            },
            handle,
        )
    with open(LauncherConfig.SESSION_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"session": {"engine_mode": "PAPER", "market_regime": "TRENDING", "risk_status": "GREEN"}}, handle)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"status": "RUNNING", "last_heartbeat": "2026-06-29T00:00:00Z"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json"), "w", encoding="utf-8") as handle:
        json.dump(
            [
                {
                    "strategy_id": "trend",
                    "asset_class": "equities",
                    "symbol": "SPY",
                    "market_regime": "trending",
                    "timestamp_close": "2026-06-28T10:00:00Z",
                    "realized_pnl": 120.0,
                },
                {
                    "strategy_id": "carry",
                    "asset_class": "fx",
                    "symbol": "EUR_USD",
                    "market_regime": "low_volatility",
                    "timestamp_close": "2026-06-28T11:00:00Z",
                    "realized_pnl": 40.0,
                },
            ],
            handle,
        )


def test_adaptive_portfolio_dashboard_api_routes_return_safe_responses(launcher_temp_dir) -> None:
    _write_phase130_artifacts()

    routes = [
        "/api/adaptive-portfolio",
        "/api/strategy-attribution",
        "/api/regime-aware-allocation",
        "/api/portfolio-risk-committee",
    ]
    payloads = []
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200
        payloads.append(response.json())

    assert payloads[0]["advisory_only"] is True
    assert payloads[0]["adaptive_recommendation"] in {"INCREASE_RISK", "MAINTAIN", "REDUCE_RISK", "PAUSE_NEW_TRADES"}
    assert payloads[2]["advisory_only"] is True
    assert round(sum(payloads[2]["regime_adjusted_allocations"].values()), 2) == 100.0
    assert payloads[3]["advisory_only"] is True


def test_mobile_dashboard_contains_adaptive_portfolio_section(launcher_temp_dir) -> None:
    _write_phase130_artifacts()

    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="adaptive-portfolio-card"' in html
    assert 'id="ap-recommendation"' in html
    assert 'id="ap-committee-status"' in html
    assert 'id="ap-committee-decision"' in html
    assert 'id="ap-top-contributors"' in html
    assert 'id="portfolio-intelligence-card"' in html


def test_mobile_dashboard_adaptive_portfolio_data_unavailable_fallback(launcher_temp_dir) -> None:
    response = client.get("/mobile")

    assert response.status_code == 200
    assert 'id="adaptive-portfolio-card"' in response.text
    assert 'id="adaptive-portfolio-unavailable"' in response.text
    assert "DATA UNAVAILABLE" in response.text


def test_adaptive_portfolio_routes_do_not_create_trade_requests(launcher_temp_dir) -> None:
    _write_phase130_artifacts()
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    client.get("/api/adaptive-portfolio")
    client.get("/api/strategy-attribution")
    client.get("/api/regime-aware-allocation")
    client.get("/api/portfolio-risk-committee")
    client.get("/mobile")

    assert not os.path.exists(trade_request_path)
