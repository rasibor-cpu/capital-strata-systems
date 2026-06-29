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


def _write_dashboard_artifacts() -> None:
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
        json.dump({"status": "RUNNING", "last_heartbeat": "2026-06-29T11:59:30Z"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_policy_profile.json"), "w", encoding="utf-8") as handle:
        json.dump({"profile": "GROWTH"}, handle)
    with open(os.path.join(LauncherConfig.ARTIFACTS_DIR, "trade_outcomes.json"), "w", encoding="utf-8") as handle:
        json.dump([{"strategy_id": "trend", "asset_class": "equities", "symbol": "SPY", "realized_pnl": 120.0}], handle)


def _write_validation_checkpoints() -> str:
    path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "validation", "paper_validation_checkpoints.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = [
        {
            "session_id": "paper-api",
            "timestamp": "2026-06-29T10:00:00Z",
            "cycle_count": 1,
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "recommendation_stability": 90.0,
            "pipeline_latency_ms": 100.0,
            "dashboard_latency_ms": 50.0,
        },
        {
            "session_id": "paper-api",
            "timestamp": "2026-06-29T10:05:00Z",
            "cycle_count": 2,
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "recommendation_stability": 92.0,
            "pipeline_latency_ms": 120.0,
            "dashboard_latency_ms": 60.0,
        },
    ]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def test_phase135a_api_get_endpoints_are_safe_and_read_only(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()
    checkpoint_path = _write_validation_checkpoints()
    before = os.path.getsize(checkpoint_path)
    decision_package_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "portfolio_decision_packages.json")
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    readiness = client.get("/api/validation-readiness")
    summary = client.get("/api/paper-validation-summary")
    checkpoints = client.get("/api/paper-validation-checkpoints")

    assert readiness.status_code == 200
    assert summary.status_code == 200
    assert checkpoints.status_code == 200
    assert readiness.json()["paper_validation_only"] is True
    assert summary.json()["final_validation_status"] == "GREEN"
    assert checkpoints.json()["count"] == 2
    assert os.path.getsize(checkpoint_path) == before
    assert not os.path.exists(decision_package_path)
    assert not os.path.exists(trade_request_path)


def test_phase135a_explicit_post_records_checkpoint(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()

    response = client.post(
        "/api/paper-validation-checkpoint/record",
        json={
            "session_id": "paper-post",
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "cycle_count": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "OK"
    assert client.get("/api/paper-validation-checkpoints").json()["count"] == 1


def test_phase135a_dashboard_renders_paper_validation(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()
    _write_validation_checkpoints()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="paper-validation-card"' in html
    assert 'id="pv-readiness-status"' in html
    assert 'id="pv-validation-status"' in html
    assert 'id="pv-session-duration"' in html
    assert 'id="pv-cycle-count"' in html
    assert 'id="pv-restart-count"' in html
    assert 'id="pv-recovery-count"' in html
    assert 'id="pv-alert-count"' in html
    assert 'id="pv-error-count"' in html
    assert 'id="pv-recommendation-stability"' in html
    assert 'id="pv-latency-summary"' in html
    assert 'id="pv-blockers"' in html
    assert 'id="pv-warnings"' in html


def test_phase135a_dashboard_data_unavailable_fallback(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()

    response = client.get("/mobile")
    summary = client.get("/api/paper-validation-summary").json()

    assert response.status_code == 200
    assert 'id="paper-validation-unavailable"' in response.text
    assert summary["status"] == "DATA UNAVAILABLE"
    assert summary["final_validation_status"] == "RED"
