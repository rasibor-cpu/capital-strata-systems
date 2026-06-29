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


def _decision_package_path() -> str:
    return os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "portfolio_decision_packages.json")


def _write_phase133_artifacts() -> None:
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
        json.dump({"session": {"engine_mode": "PAPER", "market_regime": "TRENDING_UP", "risk_status": "GREEN"}}, handle)
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


def test_get_portfolio_decision_is_read_only(launcher_temp_dir) -> None:
    _write_phase133_artifacts()

    first = client.get("/api/portfolio-decision")
    second = client.get("/api/portfolio-decision")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["advisory_only"] is True
    assert not os.path.exists(_decision_package_path())


def test_post_portfolio_decision_record_persists_one_package(launcher_temp_dir) -> None:
    _write_phase133_artifacts()

    response = client.post("/api/portfolio-decision/record")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recorded"] is True
    assert payload["count"] == 1
    with open(_decision_package_path(), "r", encoding="utf-8") as handle:
        stored = json.load(handle)
    assert len(stored) == 1
    assert stored[0]["advisory_only"] is True


def test_repeated_gets_do_not_grow_recorded_history(launcher_temp_dir) -> None:
    _write_phase133_artifacts()
    client.post("/api/portfolio-decision/record")

    for _ in range(3):
        client.get("/api/portfolio-decision")

    with open(_decision_package_path(), "r", encoding="utf-8") as handle:
        stored = json.load(handle)
    assert len(stored) == 1


def test_post_portfolio_decision_record_recovers_from_corrupt_file(launcher_temp_dir) -> None:
    _write_phase133_artifacts()
    os.makedirs(os.path.dirname(_decision_package_path()), exist_ok=True)
    with open(_decision_package_path(), "w", encoding="utf-8") as handle:
        handle.write("{bad json")

    response = client.post("/api/portfolio-decision/record")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    with open(_decision_package_path(), "r", encoding="utf-8") as handle:
        stored = json.load(handle)
    assert len(stored) == 1
