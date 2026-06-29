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

        LauncherConfig.ARTIFACTS_DIR = os.path.join(td, "artifacts")
        LauncherConfig.ACCOUNT_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_account_state_pcnrass.json")
        LauncherConfig.SESSION_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_session_state_pcnrass.json")
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = os.path.join(td, "audit_logs", "closed_trades.jsonl")
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)

        yield td

        LauncherConfig.ARTIFACTS_DIR = original_artifacts
        LauncherConfig.ACCOUNT_STATE_FILE = original_account
        LauncherConfig.SESSION_STATE_FILE = original_session
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = original_ledger


def _write_account_state(positions: list[dict]) -> None:
    with open(LauncherConfig.ACCOUNT_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "account_balance": 25000.0,
                "total_equity": 100000.0,
                "buying_power": 50000.0,
                "positions": positions,
            },
            handle,
        )


def test_portfolio_intelligence_and_capital_rotation_api_routes(launcher_temp_dir) -> None:
    _write_account_state(
        [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 50000.0},
            {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 30000.0},
            {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 20000.0},
        ]
    )

    intelligence_response = client.get("/api/portfolio-intelligence")
    rotation_response = client.get("/api/capital-rotation")

    assert intelligence_response.status_code == 200
    assert rotation_response.status_code == 200
    intelligence = intelligence_response.json()
    rotation = rotation_response.json()
    assert intelligence["status"] == "OK"
    assert intelligence["advisory_only"] is True
    assert intelligence["execution_allowed"] is False
    assert rotation["status"] == "OK"
    assert rotation["advisory_only"] is True
    assert rotation["execution_allowed"] is False
    assert sum(rotation["target_allocations"].values()) == 100.0


def test_mobile_dashboard_shows_portfolio_intelligence_metrics(launcher_temp_dir) -> None:
    _write_account_state(
        [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 50000.0},
            {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 30000.0},
            {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 20000.0},
        ]
    )

    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="portfolio-intelligence-card"' in html
    assert 'id="pi-score"' in html
    assert 'id="pi-recommendation"' in html
    assert 'id="capital-rotation-targets"' in html


def test_mobile_dashboard_uses_data_unavailable_fallback(launcher_temp_dir) -> None:
    response = client.get("/mobile")
    assert response.status_code == 200
    html = response.text
    assert 'id="portfolio-intelligence-card"' in html
    assert "DATA UNAVAILABLE" in html


def test_portfolio_intelligence_routes_do_not_execute_trade_request(launcher_temp_dir) -> None:
    trade_request_path = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_mobile_trade_requests.jsonl")

    client.get("/api/portfolio-intelligence")
    client.get("/api/capital-rotation")
    client.get("/mobile")

    assert not os.path.exists(trade_request_path)
