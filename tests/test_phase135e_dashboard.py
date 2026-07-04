from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
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


def _write_runtime(
    *,
    age_seconds: int = 300,
    max_seconds: int = 86400,
    quiet: bool = False,
    engine_mode: str = "PAPER",
    broker_mode: str = "PAPER",
    broker_execution_enabled: bool = False,
) -> None:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(seconds=age_seconds)).isoformat()
    now_text = now.isoformat()
    Path(LauncherConfig.ACCOUNT_STATE_FILE).write_text(
        json.dumps({"account_balance": 100000.0, "total_equity": 100000.0, "positions": []}),
        encoding="utf-8",
    )
    Path(LauncherConfig.SESSION_STATE_FILE).write_text(
        json.dumps(
            {
                "session": {
                    "engine_mode": engine_mode,
                    "broker_mode": broker_mode,
                    "broker_execution_enabled": broker_execution_enabled,
                    "start_time": start,
                    "last_heartbeat": now_text,
                    "max_session_seconds": max_seconds,
                    "session_expired_quiet_mode": quiet,
                }
            }
        ),
        encoding="utf-8",
    )
    Path(LauncherConfig.SUPERVISOR_STATE_FILE).write_text(
        json.dumps({"status": "RUNNING", "last_heartbeat": now_text, "restart_count": 0}),
        encoding="utf-8",
    )


def test_phase135e_session_continuity_endpoint_safe_json(launcher_temp_dir) -> None:
    _write_runtime()

    response = client.get("/api/runtime-session-continuity")
    payload = response.json()

    assert response.status_code == 200
    assert payload["session_continuity_status"] == "ACTIVE"
    assert payload["can_live_execute"] is False
    assert payload["execution_allowed"] is False


def test_phase135e_expired_live_session_endpoint_no_crash_and_blocks_readiness(launcher_temp_dir) -> None:
    _write_runtime(
        age_seconds=3700,
        max_seconds=3600,
        quiet=True,
        engine_mode="LIVE",
        broker_mode="LIVE",
        broker_execution_enabled=True,
    )

    continuity = client.get("/api/runtime-session-continuity").json()
    readiness = client.get("/api/validation-readiness").json()

    assert continuity["session_continuity_status"] == "REAUTH_REQUIRED"
    assert continuity["reauth_required"] is True
    assert readiness["readiness_status"] == "NOT_READY"
    assert "session_reauthentication_required" in readiness["blockers"]


def test_phase135e_dashboard_renders_session_continuity_fields(launcher_temp_dir) -> None:
    _write_runtime()

    response = client.get("/mobile")

    assert response.status_code == 200
    html = response.text
    assert 'id="session-continuity-card"' in html
    assert 'id="sc-status"' in html
    assert 'id="sc-reauth-required"' in html
    assert 'id="sc-can-paper-execute"' in html
    assert 'id="sc-can-live-execute"' in html
