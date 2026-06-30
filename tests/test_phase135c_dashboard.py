from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
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


def _write_zero_position_runtime() -> None:
    now = datetime.now(timezone.utc).isoformat()
    with open(LauncherConfig.ACCOUNT_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"account_balance": 100000.0, "total_equity": 100000.0, "positions": []}, handle)
    with open(LauncherConfig.SESSION_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "session": {
                    "engine_mode": "PAPER",
                    "market_regime": "RANGING",
                    "risk_status": "GREEN",
                    "start_time": now,
                    "last_heartbeat": now,
                }
            },
            handle,
        )
    with open(LauncherConfig.SUPERVISOR_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"status": "RUNNING", "last_heartbeat": now, "restart_count": 0}, handle)


def test_phase135c_runtime_portfolio_apis_report_no_portfolio_without_false_red(launcher_temp_dir) -> None:
    _write_zero_position_runtime()

    state = client.get("/api/runtime-portfolio-state").json()
    decision = client.get("/api/portfolio-decision").json()
    lifecycle = client.get("/api/runtime-portfolio-lifecycle").json()
    snapshot = client.get("/api/runtime-advisory-snapshot").json()

    assert state["status"] == "OK"
    assert state["portfolio_state"] == "NO_PORTFOLIO"
    assert decision["overall_status"] == "GREEN"
    assert decision["missing_inputs"] == []
    assert lifecycle["status"] == "OK"
    assert lifecycle["portfolio_state"] == "NO_PORTFOLIO"
    assert snapshot["snapshot_status"] == "OK"
    assert "portfolio_intelligence" in snapshot["limited_components"]


def test_phase135c_runtime_health_and_readiness_endpoints_return_safe_json_for_no_portfolio(launcher_temp_dir) -> None:
    _write_zero_position_runtime()

    health_response = client.get("/api/runtime-health")
    readiness_response = client.get("/api/validation-readiness")
    health = health_response.json()
    readiness = readiness_response.json()

    assert health_response.status_code == 200
    assert readiness_response.status_code == 200
    assert health["status"] == "OK"
    assert health["runtime_health"] in {"GREEN", "AMBER"}
    assert health["portfolio_lifecycle_state"] == "NO_PORTFOLIO"
    assert health["advisory_only"] is True
    assert health["execution_allowed"] is False
    assert readiness["status"] == "OK"
    assert readiness["readiness_status"] in {"READY_WITH_CAUTION", "NOT_READY"}
    assert readiness["portfolio_lifecycle_state"] == "NO_PORTFOLIO"
    assert "portfolio_lifecycle_no_portfolio" in readiness["warnings"]
    assert readiness["execution_allowed"] is False


def test_phase135c_stale_account_state_endpoint_warning_without_500(launcher_temp_dir) -> None:
    _write_zero_position_runtime()
    old = time.time() - 600
    os.utime(LauncherConfig.ACCOUNT_STATE_FILE, (old, old))

    health_response = client.get("/api/runtime-health")
    readiness_response = client.get("/api/validation-readiness")
    health = health_response.json()
    readiness = readiness_response.json()

    assert health_response.status_code == 200
    assert readiness_response.status_code == 200
    assert health["runtime_health"] == "AMBER"
    assert "stale_account_state" in health["warnings"]
    assert readiness["readiness_status"] in {"READY_WITH_CAUTION", "NOT_READY"}
    assert "stale_account_state" in readiness["warnings"]


def test_phase135c_lifecycle_get_endpoint_has_no_persistence_side_effects(launcher_temp_dir) -> None:
    _write_zero_position_runtime()
    lifecycle_path = Path(LauncherConfig.ARTIFACTS_DIR) / "portfolio" / "runtime_portfolio_lifecycle.json"
    registry_path = Path(LauncherConfig.ARTIFACTS_DIR) / "portfolio" / "open_position_registry.json"

    response = client.get("/api/runtime-portfolio-lifecycle")

    assert response.status_code == 200
    assert not lifecycle_path.exists()
    assert not registry_path.exists()


def test_phase135c_mobile_dashboard_renders_runtime_portfolio_panel(launcher_temp_dir) -> None:
    _write_zero_position_runtime()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="runtime-portfolio-card"' in html
    assert 'id="rp-portfolio-state"' in html
    assert 'id="rp-exposure"' in html
    assert 'id="rp-open-positions"' in html
    assert "NO_PORTFOLIO" in html


def test_phase135c_new_modules_have_no_live_execution_hooks() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "backend" / "runtime" / "runtime_portfolio_lifecycle.py",
        root / "backend" / "portfolio" / "open_position_registry.py",
        root / "backend" / "portfolio" / "runtime_exposure_builder.py",
    ]
    forbidden = ("submit_" + "order", "execute_" + "trade", "enable_" + "live", "live_" + "order")

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert not any(term in text for term in forbidden)
