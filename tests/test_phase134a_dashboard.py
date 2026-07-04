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


def _write_observability_artifacts() -> None:
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
        json.dump({"session": {"engine_mode": "PAPER", "start_time": "2026-06-29T11:00:00Z", "market_regime": "TRENDING_UP"}}, handle)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"status": "RUNNING", "last_heartbeat": "2026-06-29T11:59:30Z", "restart_count": 0, "recovery_count": 0}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_policy_profile.json"), "w", encoding="utf-8") as handle:
        json.dump({"profile": "GROWTH"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json"), "w", encoding="utf-8") as handle:
        json.dump(
            [
                {"strategy_id": "trend", "asset_class": "equities", "symbol": "SPY", "realized_pnl": 120.0},
                {"strategy_id": "carry", "asset_class": "fx", "symbol": "EUR_USD", "realized_pnl": -20.0},
                {"strategy_id": "trend", "asset_class": "equities", "symbol": "QQQ", "realized_pnl": 90.0},
            ],
            handle,
        )


def test_phase134a_api_responses_are_safe_and_read_only(launcher_temp_dir) -> None:
    _write_observability_artifacts()
    decision_package_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "portfolio_decision_packages.json")
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    performance = client.get("/api/runtime-performance")
    session = client.get("/api/session-validation")
    health = client.get("/api/runtime-health")

    assert performance.status_code == 200
    assert session.status_code == 200
    assert health.status_code == 200
    assert performance.json()["advisory_only"] is True
    assert session.json()["advisory_only"] is True
    assert health.json()["advisory_only"] is True
    assert not os.path.exists(decision_package_path)
    assert not os.path.exists(trade_request_path)


def test_phase134a_dashboard_renders_operational_health(launcher_temp_dir) -> None:
    _write_observability_artifacts()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="operational-health-card"' in html
    assert 'id="oh-runtime-health"' in html
    assert 'id="oh-session-status"' in html
    assert 'id="oh-pipeline-latency"' in html
    assert 'id="oh-dashboard-latency"' in html
    assert 'id="oh-cache-hit-rate"' in html
    assert 'id="oh-heartbeat-age"' in html
    assert 'id="oh-restart-count"' in html
    assert 'id="oh-recovery-count"' in html
    assert 'id="oh-memory-usage"' in html
    assert 'id="oh-cpu-usage"' in html
    assert 'id="oh-overall-health"' in html


def test_phase134a_data_unavailable_fallback(launcher_temp_dir) -> None:
    response = client.get("/mobile")
    session = client.get("/api/session-validation").json()
    health = client.get("/api/runtime-health").json()

    assert response.status_code == 200
    assert "DATA UNAVAILABLE" in response.text
    assert session["advisory_only"] is True
    assert health["advisory_only"] is True
    assert health["execution_allowed"] is False
