from __future__ import annotations

import json
import os
import tempfile
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
        original = (
            LauncherConfig.ARTIFACTS_DIR,
            LauncherConfig.ACCOUNT_STATE_FILE,
            LauncherConfig.SESSION_STATE_FILE,
            LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
            LauncherConfig.SUPERVISOR_STATE_FILE,
        )
        LauncherConfig.ARTIFACTS_DIR = os.path.join(td, "artifacts")
        LauncherConfig.ACCOUNT_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_account_state_pcnrass.json")
        LauncherConfig.SESSION_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_session_state_pcnrass.json")
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = os.path.join(td, "audit_logs", "closed_trades.jsonl")
        LauncherConfig.SUPERVISOR_STATE_FILE = os.path.join(td, "runtime", "supervisor", "css_runtime_supervisor_state.json")
        os.makedirs(LauncherConfig.ARTIFACTS_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(LauncherConfig.CLOSED_TRADE_LEDGER_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(LauncherConfig.SUPERVISOR_STATE_FILE), exist_ok=True)
        yield td
        (
            LauncherConfig.ARTIFACTS_DIR,
            LauncherConfig.ACCOUNT_STATE_FILE,
            LauncherConfig.SESSION_STATE_FILE,
            LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
            LauncherConfig.SUPERVISOR_STATE_FILE,
        ) = original


def _write_runtime() -> None:
    now = datetime.now(timezone.utc).isoformat()
    Path(LauncherConfig.ACCOUNT_STATE_FILE).write_text(
        json.dumps({"account_balance": 100000.0, "total_equity": 100000.0, "positions": []}),
        encoding="utf-8",
    )
    Path(LauncherConfig.SESSION_STATE_FILE).write_text(
        json.dumps({"session": {"engine_mode": "PAPER", "start_time": now, "last_heartbeat": now, "max_session_seconds": 86400}}),
        encoding="utf-8",
    )
    Path(LauncherConfig.SUPERVISOR_STATE_FILE).write_text(
        json.dumps({"status": "RUNNING", "last_heartbeat": now, "restart_count": 0}),
        encoding="utf-8",
    )
    Path(LauncherConfig.CLOSED_TRADE_LEDGER_PATH).write_text("", encoding="utf-8")


def test_phase135d_runtime_artifact_freshness_endpoint_safe_json(launcher_temp_dir) -> None:
    _write_runtime()

    response = client.get("/api/runtime-artifact-freshness")
    payload = response.json()

    assert response.status_code == 200
    assert payload["freshness_status"] in {"GREEN", "AMBER"}
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert "closed_trade_ledger" in payload["artifacts"]


def test_phase135d_dashboard_renders_freshness_fields(launcher_temp_dir) -> None:
    _write_runtime()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="oh-artifact-freshness-status"' in html
    assert 'id="oh-stale-artifacts"' in html
    assert 'id="oh-refreshed-artifacts"' in html
    assert 'id="oh-ledger-freshness"' in html
    assert 'id="rp-account-freshness"' in html
