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
        json.dump(
            [
                {"strategy_id": "trend", "asset_class": "equities", "symbol": "SPY", "realized_pnl": 120.0},
                {"strategy_id": "carry", "asset_class": "fx", "symbol": "EUR_USD", "realized_pnl": -20.0},
            ],
            handle,
        )


def _write_recommendation_history() -> str:
    path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "recommendation_tracker.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = [
        {
            "recommendation": "INCREASE_RISK",
            "confidence": 0.8,
            "policy_profile": "growth",
            "market_regime": "TRENDING_UP",
            "asset_class": "equities",
            "strategy": "trend",
            "outcome": {"realized_return": 0.04, "max_drawdown": 0.02},
        },
        {
            "recommendation": "REDUCE_RISK",
            "confidence": 0.7,
            "policy_profile": "balanced",
            "market_regime": "HIGH_VOLATILITY",
            "asset_class": "fx",
            "strategy": "carry",
            "outcome": {"realized_return": -0.03, "max_drawdown": 0.08},
        },
        {
            "recommendation": "MAINTAIN",
            "confidence": 0.5,
            "policy_profile": "growth",
            "market_regime": "TRENDING_UP",
            "asset_class": "equities",
            "strategy": "trend",
            "outcome": {"realized_return": -0.005, "max_drawdown": 0.01},
        },
    ]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def test_phase134b_api_responses_are_read_only(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()
    history_path = _write_recommendation_history()
    before_size = os.path.getsize(history_path)
    decision_package_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "portfolio", "portfolio_decision_packages.json")
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    evaluation = client.get("/api/recommendation-evaluation")
    calibration = client.get("/api/confidence-calibration")
    drift = client.get("/api/recommendation-drift")

    assert evaluation.status_code == 200
    assert calibration.status_code == 200
    assert drift.status_code == 200
    assert evaluation.json()["status"] == "OK"
    assert calibration.json()["status"] == "OK"
    assert drift.json()["status"] == "OK"
    assert evaluation.json()["advisory_only"] is True
    assert calibration.json()["execution_allowed"] is False
    assert os.path.getsize(history_path) == before_size
    assert not os.path.exists(decision_package_path)
    assert not os.path.exists(trade_request_path)


def test_phase134b_dashboard_renders_recommendation_evaluation(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()
    _write_recommendation_history()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="recommendation-evaluation-card"' in html
    assert 'id="re-accuracy"' in html
    assert 'id="re-calibration-score"' in html
    assert 'id="re-drift-score"' in html
    assert 'id="re-avoided-loss"' in html
    assert 'id="re-missed-opportunity"' in html
    assert 'id="re-stability"' in html
    assert 'id="re-evaluation-confidence"' in html


def test_phase134b_dashboard_data_unavailable_fallback(launcher_temp_dir) -> None:
    _write_dashboard_artifacts()

    response = client.get("/mobile")
    evaluation = client.get("/api/recommendation-evaluation").json()
    calibration = client.get("/api/confidence-calibration").json()
    drift = client.get("/api/recommendation-drift").json()

    assert response.status_code == 200
    assert 'id="recommendation-evaluation-unavailable"' in response.text
    assert evaluation["status"] == "DATA UNAVAILABLE"
    assert calibration["status"] == "DATA UNAVAILABLE"
    assert drift["status"] == "DATA UNAVAILABLE"
