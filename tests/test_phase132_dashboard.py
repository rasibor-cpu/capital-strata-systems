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


def _write_phase132_artifacts() -> None:
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
        json.dump({"profile": "GROWTH"}, handle)
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


def test_phase132_dashboard_api_routes_return_safe_responses(launcher_temp_dir) -> None:
    _write_phase132_artifacts()

    routes = [
        "/api/portfolio-decision",
        "/api/decision-validation",
        "/api/explainability",
        "/api/advisory-consistency",
    ]
    payloads = []
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200
        payloads.append(response.json())

    assert payloads[0]["advisory_only"] is True
    assert payloads[0]["overall_status"] in {"GREEN", "AMBER", "RED"}
    assert payloads[1]["validation_status"] in {"PASS", "WARN", "FAIL"}
    assert payloads[2]["primary_explanation"]
    assert payloads[3]["advisory_only"] is True


def test_phase132_dashboard_html_contains_decision_summary(launcher_temp_dir) -> None:
    _write_phase132_artifacts()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="portfolio-decision-card"' in html
    assert 'id="pd-confidence"' in html
    assert 'id="pd-validation-status"' in html
    assert 'id="pd-consistency-status"' in html
    assert 'id="pd-primary-explanation"' in html
    assert 'id="portfolio-intelligence-card"' in html
    assert 'id="adaptive-portfolio-card"' in html


def test_phase132_dashboard_fail_closed_and_no_trade_request(launcher_temp_dir) -> None:
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    decision = client.get("/api/portfolio-decision").json()
    client.get("/api/decision-validation")
    client.get("/api/explainability")
    client.get("/api/advisory-consistency")
    response = client.get("/mobile")

    assert decision["overall_status"] == "RED"
    assert decision["portfolio_recommendation"] == "PAUSE_NEW_TRADES"
    assert response.status_code == 200
    assert not os.path.exists(trade_request_path)
