from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.security.live_toggle import is_live_execution_authorized
from backend.governance.css_gate_dashboard_adapter import CSSGateDashboardAdapter
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.runtime.runtime_session_continuity import RuntimeSessionContinuityMonitor
from backend.runtime.session_renewal import SessionRenewalManager
from launcher.css_launcher_config import LauncherConfig
from launcher.css_mobile_launcher import app


NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _session(age_seconds: int, **extra):
    session = {
        "engine_mode": "PAPER",
        "broker_mode": "paper",
        "broker_execution_enabled": False,
        "start_time": (NOW - timedelta(seconds=age_seconds)).isoformat(),
        "last_activity": (NOW - timedelta(seconds=30)).isoformat(),
        "max_session_seconds": 3600,
    }
    session.update(extra)
    return {"session": session}


def test_phase140b_paper_mode_auto_renews_after_max_session_age(tmp_path, caplog) -> None:
    caplog.set_level("INFO")
    path = tmp_path / "css_session_state_pcnrass.json"
    path.write_text(json.dumps(_session(3700)), encoding="utf-8")

    result = RuntimeSessionContinuityMonitor(session_state_path=path).evaluate(
        json.loads(path.read_text(encoding="utf-8")),
        now=NOW,
    )
    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert result["session_continuity_status"] == "ACTIVE"
    assert result["reauth_required"] is False
    assert result["session_renewal_reason"] == "PAPER_SESSION_RENEWED"
    assert result["session_renewal_count"] == 1
    assert result["renewal_allowed"] is True
    assert result["live_renewal_blocked"] is False
    assert result["execution_allowed"] is False
    assert persisted["session"]["session_renewal_reason"] == "PAPER_SESSION_RENEWED"
    assert "PAPER_SESSION_RENEWED" in caplog.text


def test_phase140b_broker_execution_disabled_allows_continuous_paper_runtime() -> None:
    result = SessionRenewalManager().evaluate(_session(3700, broker_execution_enabled=False), now=NOW)

    assert result["renewed"] is True
    assert result["continuous_paper_runtime_enabled"] is True
    assert result["renewal_mode"] == "AUTO_PAPER"
    assert result["broker_execution_enabled"] is False
    assert result["execution_allowed"] is False


def test_phase140b_live_mode_cannot_auto_renew() -> None:
    renewal = SessionRenewalManager().evaluate(
        _session(3700, engine_mode="LIVE", broker_mode="live"),
        now=NOW,
    )
    continuity = RuntimeSessionContinuityMonitor().evaluate(
        _session(3700, engine_mode="LIVE", broker_mode="live"),
        now=NOW,
    )

    assert renewal["renewed"] is False
    assert renewal["renewal_allowed"] is False
    assert renewal["live_renewal_blocked"] is True
    assert "live_mode_selected" in renewal["renewal_blockers"]
    assert continuity["session_continuity_status"] == "EXPIRED"
    assert continuity["reauth_required"] is True


def test_phase140b_broker_execution_enabled_cannot_auto_renew() -> None:
    renewal = SessionRenewalManager().evaluate(
        _session(3700, broker_execution_enabled=True, broker_execution_allowed=True),
        now=NOW,
    )
    continuity = RuntimeSessionContinuityMonitor().evaluate(
        _session(3700, broker_execution_enabled=True),
        now=NOW,
    )

    assert renewal["renewed"] is False
    assert renewal["renewal_allowed"] is False
    assert renewal["live_renewal_blocked"] is True
    assert "broker_execution_enabled" in renewal["renewal_blockers"]
    assert continuity["session_continuity_status"] == "EXPIRED"
    assert continuity["reauth_required"] is True


def test_phase140b_expired_live_session_still_blocks_trading() -> None:
    decision = CSSUnifiedTradeGate().approve_trade(
        candidate={
            "asset_class": "crypto",
            "symbol": "BTC-USD",
            "expected_value": 10,
            "cost": 1,
            "probability": 0.9,
        },
        session={"role": "SUPER_USER", "created": time.time() - 3700},
        portfolio_state={"crypto": 0},
        engine_mode="BALANCED",
    )

    assert decision.approved is False
    assert decision.reason == "rejected: session expired"


def test_phase140b_rbac_and_live_permissions_remain_unchanged() -> None:
    denied, denied_reason, _ = is_live_execution_authorized(
        {
            "user_id": "operator",
            "role": "TRADER",
            "role_profile": {"can_execute_live_trading": False},
        }
    )
    allowed, allowed_reason, _ = is_live_execution_authorized(
        {
            "user_id": "operator",
            "role": "TRADER",
            "role_profile": {"can_execute_live_trading": True},
        }
    )

    assert denied is False
    assert denied_reason == "live_toggle_rbac_denied"
    assert allowed is True
    assert allowed_reason == "live_toggle_permission_authorized:can_execute_live_trading"


def test_phase140b_unified_trade_gate_still_blocks_unauthorized_live_trades() -> None:
    adapter = CSSGateDashboardAdapter(CSSUnifiedTradeGate())
    decision = adapter.approve_trade(
        candidate={
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "broker_mode": "live",
            "signal_score": 12,
            "prob_positive": 0.9,
        },
        session={"session_id": "session-140b", "role": "TRADER", "created": time.time()},
        role_profile={
            "role": "TRADER",
            "can_use_live_broker_mode": True,
            "can_execute_live_trading": False,
        },
        portfolio_state={"CRYPTO": 0},
        engine_mode="BALANCED",
    )

    assert decision["approved"] is False
    assert decision["reason"] == "RBAC_BLOCKED_LIVE_EXECUTION"


def test_phase140b_session_renewal_status_api_is_read_only(tmp_path) -> None:
    original = (
        LauncherConfig.ARTIFACTS_DIR,
        LauncherConfig.SESSION_STATE_FILE,
        LauncherConfig.ACCOUNT_STATE_FILE,
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
        LauncherConfig.SUPERVISOR_STATE_FILE,
    )
    try:
        LauncherConfig.ARTIFACTS_DIR = str(tmp_path / "artifacts")
        LauncherConfig.SESSION_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_session_state_pcnrass.json")
        LauncherConfig.ACCOUNT_STATE_FILE = os.path.join(LauncherConfig.ARTIFACTS_DIR, "css_account_state_pcnrass.json")
        LauncherConfig.CLOSED_TRADE_LEDGER_PATH = str(tmp_path / "audit_logs" / "closed_trades.jsonl")
        LauncherConfig.SUPERVISOR_STATE_FILE = str(tmp_path / "runtime" / "supervisor" / "css_runtime_supervisor_state.json")
        Path(LauncherConfig.ARTIFACTS_DIR).mkdir(parents=True, exist_ok=True)
        Path(LauncherConfig.SESSION_STATE_FILE).write_text(json.dumps(_session(3700)), encoding="utf-8")

        response = TestClient(app, raise_server_exceptions=False).get("/api/session-renewal-status")
        payload = response.json()
        persisted = json.loads(Path(LauncherConfig.SESSION_STATE_FILE).read_text(encoding="utf-8"))

        assert response.status_code == 200
        assert payload["renewal_allowed"] is True
        assert payload["renewed"] is True
        assert payload["execution_allowed"] is False
        assert "session_renewal_count" not in persisted["session"]
    finally:
        (
            LauncherConfig.ARTIFACTS_DIR,
            LauncherConfig.SESSION_STATE_FILE,
            LauncherConfig.ACCOUNT_STATE_FILE,
            LauncherConfig.CLOSED_TRADE_LEDGER_PATH,
            LauncherConfig.SUPERVISOR_STATE_FILE,
        ) = original
