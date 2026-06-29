from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

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


def _write_runtime_artifacts() -> None:
    with open(LauncherConfig.ACCOUNT_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "account_balance": 25000.0,
                "total_equity": 100000.0,
                "positions": [
                    {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 60000.0},
                    {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 40000.0},
                ],
            },
            handle,
        )
    with open(LauncherConfig.SESSION_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"session": {"engine_mode": "PAPER", "market_regime": "TRENDING_UP", "risk_status": "GREEN"}}, handle)
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"status": "RUNNING", "last_heartbeat": "2026-06-29T11:59:30Z", "restart_count": 0}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_policy_profile.json"), "w", encoding="utf-8") as handle:
        json.dump({"profile": "GROWTH"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json"), "w", encoding="utf-8") as handle:
        json.dump(
            [
                {"strategy_id": "trend", "asset_class": "EQUITIES", "symbol": "SPY", "realized_pnl": 120.0},
                {"strategy_id": "carry", "asset_class": "FX", "symbol": "EUR_USD", "realized_pnl": -20.0},
                {"strategy_id": "trend", "asset_class": "EQUITIES", "symbol": "QQQ", "realized_pnl": 90.0},
            ],
            handle,
        )


def test_phase135b_runtime_artifacts_populate_portfolio_decision_inputs(launcher_temp_dir) -> None:
    _write_runtime_artifacts()

    decision = client.get("/api/portfolio-decision").json()
    state = client.get("/api/runtime-portfolio-state").json()
    snapshot = client.get("/api/runtime-advisory-snapshot").json()

    assert state["status"] == "OK"
    assert decision["overall_status"] in {"GREEN", "AMBER", "RED"}
    assert decision["missing_inputs"] == []
    assert decision["advisory_only"] is True
    assert decision["execution_allowed"] is False
    assert snapshot["snapshot_status"] == "OK"
    assert snapshot["missing_components"] == []


def test_phase135b_api_get_endpoints_are_read_only(launcher_temp_dir) -> None:
    _write_runtime_artifacts()
    decision_package_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "portfolio_decision_packages.json")
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    assert client.get("/api/runtime-portfolio-state").status_code == 200
    assert client.get("/api/runtime-advisory-snapshot").status_code == 200
    assert client.get("/api/runtime-health").status_code == 200
    assert client.get("/api/validation-readiness").status_code == 200

    assert not os.path.exists(decision_package_path)
    assert not os.path.exists(trade_request_path)


def test_phase135b_missing_runtime_artifacts_remain_fail_closed(launcher_temp_dir) -> None:
    decision = client.get("/api/portfolio-decision").json()
    state = client.get("/api/runtime-portfolio-state").json()
    snapshot = client.get("/api/runtime-advisory-snapshot").json()
    readiness = client.get("/api/validation-readiness").json()

    assert state["status"] == "DATA UNAVAILABLE"
    assert decision["overall_status"] == "RED"
    assert decision["missing_inputs"]
    assert snapshot["snapshot_status"] in {"PARTIAL", "DATA UNAVAILABLE"}
    assert readiness["readiness_status"] == "NOT_READY"


def test_phase135b_dashboard_renders_runtime_advisory_integration(launcher_temp_dir) -> None:
    _write_runtime_artifacts()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="runtime-advisory-card"' in html
    assert 'id="rai-runtime-state-status"' in html
    assert 'id="rai-snapshot-status"' in html
    assert 'id="rai-available-components"' in html
    assert 'id="rai-missing-components"' in html
    assert 'id="rai-missing-input-reasons"' in html
    assert 'id="rai-portfolio-decision-status"' in html


def test_phase135b_new_code_has_no_execution_hooks() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "backend" / "portfolio" / "runtime_portfolio_state_builder.py",
        root / "backend" / "portfolio" / "runtime_advisory_snapshot.py",
    ]
    forbidden = ("submit_" + "order", "execute_" + "trade", "enable_" + "live", "live_" + "order")

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert not any(term in text for term in forbidden)
