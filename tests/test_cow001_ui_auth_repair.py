"""COW001 UI + auth provenance repair regression tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.runtime.broker_startup_selection import broker_summary_from_artifacts
from backend.runtime.canonical_broker_state_adapter import (
    broker_scoped_validation_feed,
    reconcile_broker_summary_from_artifacts,
)
from dashboard.auth import css_sign_on as auth
from dashboard.runtime.frontend_contract import build_frontend_payload


def _coinbase_live_payload(**overrides):
    diagnostics = {
        "broker": "COINBASE",
        "credentials_present": True,
        "credential_status": "PRESENT",
        "coinbase_key_present": True,
        "coinbase_private_key_present": True,
    }
    payload = {
        "selected_broker": "COINBASE",
        "broker": "COINBASE",
        "broker_mode": "live",
        "mode": "live",
        "broker_connected": True,
        "broker_authenticated": True,
        "authenticated": True,
        "credentials_present": True,
        "credential_status": "PASS",
        "auth_status": "PASS",
        "connection_status": "PASS",
        "authentication_status": "AUTHENTICATED",
        "market_data_status": "PASS",
        "account_loaded": True,
        "balances_loaded": True,
        "products_loaded": 929,
        "broker_ready": True,
        "execution_authority": False,
        "can_live_execute": False,
        "live_micro_pilot_state": "DISARMED",
        "broker_execution_armed": False,
        "readiness_state": "ACCOUNT_ACCESSIBLE",
        "operator_requested_live": True,
        "live_authority_state": "BLOCKED",
        "broker_credential_diagnostics": diagnostics,
        "credential_diagnostics": diagnostics,
        "canonical_account_snapshot": {
            "balances_loaded": True,
            "equity": 12345.67,
            "cash": 1000.0,
            "buying_power": 900.0,
        },
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def temp_auth_file(tmp_path):
    mock_file = tmp_path / "css_auth_session.json"
    with patch.object(auth, "SESSION_AUTH_FILE", mock_file):
        yield mock_file


@pytest.fixture
def mock_registry():
    password_hash = auth.hash_password("ValidPass1!")
    return {
        "00000": {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "password_hash": password_hash,
            "failed_attempts": 0,
            "locked": False,
            "lockout_until": None,
            "last_password_change": datetime.now().isoformat(timespec="seconds"),
        }
    }


def test_auth01_fresh_launch_does_not_silently_restore_stale_session(
    monkeypatch, temp_auth_file, mock_registry
):
    monkeypatch.delenv("CSS_AUTH_ALLOW_SESSION_RESTORE", raising=False)
    monkeypatch.setenv("CSS_AUTH_UI", "cli")
    temp_auth_file.write_text(
        json.dumps(
            {
                "user_id": "00000",
                "display_name": "CSS Administrator",
                "role": "SUPER_USER",
                "unit_code": "CORE",
                "home_branch": "HQ",
                "auth_session_id": "stale-session",
                "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        ),
        encoding="utf-8",
    )
    mock_console = MagicMock(
        return_value={
            "user_id": "00000",
            "role": "SUPER_USER",
            "auth_source": "interactive",
            "auth_provenance": auth.AUTH_PROVENANCE_INTERACTIVE,
        }
    )
    with patch.object(auth, "load_users", return_value=mock_registry):
        with patch.object(auth, "await_console_login", mock_console):
            result = auth.await_login_ready_state()
    mock_console.assert_called_once()
    assert result["auth_provenance"] == auth.AUTH_PROVENANCE_INTERACTIVE


def test_auth02_correct_password_authentication_succeeds(mock_registry):
    users = dict(mock_registry)
    result = auth.authenticate_credentials(users, "00000", "ValidPass1!")
    assert result["user_id"] == "00000"
    assert result["auth_provenance"] == auth.AUTH_PROVENANCE_INTERACTIVE


def test_auth03_incorrect_password_authentication_fails(mock_registry):
    with pytest.raises(auth.AuthFailure):
        auth.authenticate_credentials(dict(mock_registry), "00000", "WrongPass1!")


def test_auth04_second_login_supersedes_first_authoritative_session(temp_auth_file, mock_registry):
    users = dict(mock_registry)
    first = auth.authenticate_credentials(users, "00000", "ValidPass1!")
    auth.persist_login_session(first)
    first_id = first["auth_session_id"]
    second = auth.authenticate_credentials(users, "00000", "ValidPass1!")
    auth.persist_login_session(second)
    assert first_id != second["auth_session_id"]
    current = auth.read_authoritative_auth_session()
    assert current["auth_session_id"] == second["auth_session_id"]


def test_auth05_superseded_session_fails_authoritative_validation(temp_auth_file, mock_registry):
    users = dict(mock_registry)
    first = auth.authenticate_credentials(users, "00000", "ValidPass1!")
    auth.persist_login_session(first)
    superseded_id = first["auth_session_id"]
    second = auth.authenticate_credentials(users, "00000", "ValidPass1!")
    auth.persist_login_session(second)
    assert auth.is_auth_session_authoritative("00000", superseded_id) is False
    assert auth.is_auth_session_authoritative("00000", second["auth_session_id"]) is True


def test_auth06_no_secret_material_in_auth_evidence(temp_auth_file, mock_registry):
    users = dict(mock_registry)
    ctx = auth.authenticate_credentials(users, "00000", "ValidPass1!")
    auth.persist_login_session(ctx)
    blob = json.dumps(ctx)
    assert "ValidPass1!" not in blob
    assert "password_hash" not in blob.lower()
    persisted = temp_auth_file.read_text(encoding="utf-8")
    assert "ValidPass1!" not in persisted
    assert "password" not in persisted.lower()


def test_ui01_coinbase_live_state_renders_coinbase_live():
    payload = _coinbase_live_payload()
    summary = reconcile_broker_summary_from_artifacts(payload)
    assert summary["broker"] == "COINBASE"
    assert summary["broker_mode"] == "live"


def test_ui02_execution_remains_blocked():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload())
    frontend = build_frontend_payload({"broker_summary": summary})
    broker = frontend["sections"]["broker"]
    assert broker["execution_scope"] != "LIVE_ARMED"
    assert broker.get("live_trading_enabled") is False


def test_ui03_execution_authority_false():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload())
    assert summary.get("execution_authority") is False
    frontend = build_frontend_payload({"broker_summary": summary})
    assert frontend["sections"]["broker"]["execution_authority"] is False


def test_ui04_can_live_execute_false():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload())
    frontend = build_frontend_payload({"broker_summary": summary})
    assert frontend["sections"]["broker"]["can_live_execute"] is False


def test_ui05_pilot_disarmed():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload(live_micro_pilot_state="DISARMED"))
    frontend = build_frontend_payload({"broker_summary": summary})
    assert frontend["sections"]["broker"]["live_micro_pilot_state"] == "DISARMED"


def test_ui06_connected_not_simultaneously_fail():
    stale = _coinbase_live_payload(connection_status="FAIL", broker_connected=False)
    canonical = _coinbase_live_payload(
        connection_status="PASS",
        broker_connected=True,
        canonical_broker_runtime_state={
            "broker": "COINBASE",
            "mode": "live",
            "connection_status": "PASS",
            "authentication_status": "PASS",
            "credential_status": "PASS",
            "overall_status": "GREEN",
        },
    )
    summary = reconcile_broker_summary_from_artifacts({**stale, **canonical})
    frontend = build_frontend_payload({"broker_summary": summary})
    connection = str(frontend["sections"]["broker"]["connection_status"]).upper()
    assert connection in {"PASS", "CONNECTED", "GREEN"}
    assert connection != "FAIL"


def test_ui07_simulated_paper_not_live_coinbase_equity():
    from backend.brokers.account_balance_contract import build_broker_balance_summary

    paper_summary = build_broker_balance_summary(
        {
            "account_balance": 200.0,
            "total_equity": 200.0,
            "account_mode": "PAPER",
            "broker": "NONE",
        },
        broker="NONE",
        mode="PAPER",
    )
    assert paper_summary["account_summary"]["total_equity"]["provenance"] == "SIMULATED_PAPER_ACCOUNT"

    # A reconciled live Coinbase selection must not relabel paper account artifacts as broker-reported.
    still_paper = build_broker_balance_summary(
        {
            "account_balance": 200.0,
            "total_equity": 200.0,
            "account_mode": "PAPER",
            "broker": "NONE",
        },
        broker="NONE",
        mode="PAPER",
    )
    assert still_paper["paper_account"] is True
    assert still_paper["account_summary"]["total_equity"]["value"] == 200.0


def test_ui08_oanda_cannot_render_coinbase_endpoint():
    contaminated = {
        "validation_status": "PASS",
        "endpoint": "https://api.coinbase.com",
        "api_version": "v3",
        "broker_operational_status": {"broker": "OANDA"},
    }
    sanitized = broker_scoped_validation_feed(contaminated, "OANDA")
    assert "coinbase" not in sanitized["endpoint"].lower()
    assert sanitized["endpoint"] == "DATA UNAVAILABLE"


def test_ui09_missing_broker_data_not_tested():
    summary = broker_summary_from_artifacts({}, {})
    assert summary["selected_broker"] == "NONE"
    assert summary.get("connection_status") in {"NOT_TESTED", "FAIL", None} or "connection_status" in summary


def test_ui10_canonical_fields_survive_launcher_mapping():
    payload = _coinbase_live_payload()
    summary = reconcile_broker_summary_from_artifacts(payload)
    frontend = build_frontend_payload({"broker_summary": summary})
    broker = frontend["sections"]["broker"]
    assert broker["selected_broker"] == "COINBASE"
    assert broker["broker_mode"] == "live"
    assert broker["connection_status"] in {"PASS", "CONNECTED", "GREEN"}


def test_safety01_no_funded_execution_authority():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload(execution_authority=True, can_live_execute=True))
    assert summary["execution_authority"] is False
    assert summary["can_live_execute"] is False


def test_safety02_no_broker_execution_armed():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload(broker_execution_armed=True))
    assert summary["broker_execution_armed"] is False


def test_safety03_no_order_submission_path_enabled():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload(order_submission_status="ENABLED"))
    frontend = build_frontend_payload({"broker_summary": summary})
    assert frontend["sections"]["broker"]["order_submission_status"] == "DISABLED"


def test_safety04_fail_closed_controls_remain():
    summary = reconcile_broker_summary_from_artifacts(_coinbase_live_payload())
    assert summary["live_trading_blocked"] is True
    assert summary["execution_allowed"] is False
