import json
import os
import sys
import time
import builtins
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock stdin and set test mode before dashboard loads.
# Automated bypass requires CSS_AUTH_TEST_PROFILE (AR-023); needed so dashboard
# import does not block on interactive sign-on during collection.
os.environ["CSS_AUTOMATED_INPUT"] = "1"
os.environ["CSS_AUTH_TEST_PROFILE"] = "1"
os.environ["CSS_TEST_MODE"] = "1"

_existing_auth_module = sys.modules.get("dashboard.auth.css_sign_on")
if _existing_auth_module is not None and (
    not isinstance(_existing_auth_module, types.ModuleType)
    or not str(getattr(_existing_auth_module, "__file__", "")).endswith("css_sign_on.py")
):
    sys.modules.pop("dashboard.auth.css_sign_on", None)
    auth_package = sys.modules.get("dashboard.auth")
    if auth_package is not None and hasattr(auth_package, "css_sign_on"):
        delattr(auth_package, "css_sign_on")

from backend.security.audit_ledger import AuditLedger
from dashboard.auth import css_sign_on as auth

pytestmark = pytest.mark.live_session

# Avoid importing scripts.css_live_dashboard at collection time — it runs a full
# automated LIVE startup when CSS_AUTOMATED_INPUT=1 and contaminates auth tests.
dashboard = None


def _dashboard():
    global dashboard
    if dashboard is None:
        from scripts import css_live_dashboard as _dash

        dashboard = _dash
    return dashboard


@pytest.fixture(autouse=True)
def reset_metrics(monkeypatch):
    """Reset AuthMetrics between tests."""
    monkeypatch.setenv("CSS_AUTOMATED_INPUT", "1")
    monkeypatch.setenv("CSS_AUTH_TEST_PROFILE", "1")
    monkeypatch.setenv("CSS_TEST_MODE", "1")
    monkeypatch.delenv("CSS_AUTH_UI", raising=False)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "1")
    _reset_auth_metrics()
    yield
    _reset_auth_metrics()


def _reset_auth_metrics() -> None:
    auth.AuthMetrics.successful_interactive_logins = 0
    auth.AuthMetrics.failed_interactive_logins = 0
    auth.AuthMetrics.restored_sessions = 0
    auth.AuthMetrics.rejected_restored_sessions = 0
    auth.AuthMetrics.expired_sessions = 0
    auth.AuthMetrics.invalidated_sessions = 0
    auth.AuthMetrics.malformed_session_files = 0
    auth.AuthMetrics.authentication_latency_history = []
    auth.AuthMetrics.restored_session_ages = []


@pytest.fixture
def temp_auth_file(tmp_path):
    mock_file = tmp_path / "css_auth_session.json"
    with patch.object(auth, "SESSION_AUTH_FILE", mock_file):
        yield mock_file


@pytest.fixture
def temp_audit_file(tmp_path):
    mock_file = tmp_path / "css_audit_log.jsonl"
    # Ensure parent dir exists
    mock_file.parent.mkdir(parents=True, exist_ok=True)

    # Patch the imported module object directly. Some legacy script tests replace
    # sys.modules["dashboard.auth.css_sign_on"] during collection, so dotted
    # patch targets can bind to a mock instead of the real auth module.
    ledger_instance = AuditLedger()
    ledger_instance.audit_file = mock_file

    with patch.object(auth, "_audit_ledger_instance", ledger_instance), patch.object(
        auth, "get_audit_ledger", return_value=ledger_instance
    ):
        yield mock_file


@pytest.fixture
def mock_registry():
    return {
        "00000": {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "password_hash": auth.hash_password("123456"),
            "locked": False,
            "lockout_until": None,
            "must_change_password": False,
            "last_password_change": datetime.now().isoformat()
        },
        "00001": {
            "user_id": "00001",
            "display_name": "Locked User",
            "role": "TRADER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "password_hash": auth.hash_password("123456"),
            "locked": True,
            "lockout_until": None,
            "must_change_password": False,
            "last_password_change": datetime.now().isoformat()
        }
    }


def test_phase183bd_auth_paths_are_unique_and_temporary(temp_auth_file, temp_audit_file):
    assert temp_auth_file.parent == temp_audit_file.parent
    assert temp_auth_file.name == "css_auth_session.json"
    assert temp_audit_file.name == "css_audit_log.jsonl"
    assert "artifacts" not in str(temp_auth_file)
    assert "artifacts" not in str(temp_audit_file)


def test_phase183bd_metrics_reset_between_auth_tests():
    assert auth.AuthMetrics.get_metrics_dict()["restored_sessions"] == 0
    auth.AuthMetrics.restored_sessions = 99


def test_phase183bd_logout_uses_injected_audit_ledger(temp_audit_file):
    auth.record_auth_audit_event(
        "logout",
        "00000",
        {"auth_source": "restored", "session_age_seconds": 5, "outcome": "SUCCESS"},
    )

    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    assert events[-1]["event_type"] == "logout"
    assert events[-1]["details"]["auth_source"] == "restored"


def test_phase183bd_pytest_cannot_open_auth_prompt(monkeypatch, temp_auth_file, mock_registry):
    monkeypatch.setenv("CSS_AUTH_UI", "cli")
    monkeypatch.setattr(auth, "load_users", lambda: mock_registry)
    monkeypatch.setattr(
        auth,
        "await_console_login",
        MagicMock(side_effect=AssertionError("console prompt forbidden")),
    )
    temp_auth_file.write_text(
        json.dumps(
            {
                "user_id": "00000",
                "display_name": "CSS Administrator",
                "role": "SUPER_USER",
                "unit_code": "CORE",
                "home_branch": "HQ",
                "last_login": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    assert auth.await_login_ready_state()["user_id"] == "00000"


@pytest.mark.live_session
def test_metrics_collection_on_restore_success(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that a successful session restore registers in metrics and logs success events."""
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "last_login": datetime.now(timezone.utc).isoformat(),
        "login_persistence": True
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is not None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["restored_sessions"] == 1
    assert metrics["rejected_restored_sessions"] == 0
    assert len(auth.AuthMetrics.authentication_latency_history) >= 1
    
    # Check audit log
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    assert len(events) >= 1
    assert events[-1]["event_type"] == "restored_session_success"
    assert events[-1]["user_id"] == "00000"


def test_metrics_collection_on_restore_expiry(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that an expired session restore registers in metrics and logs rejection and expiration events."""
    expired_time = datetime.now(timezone.utc) - timedelta(hours=30)
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "last_login": expired_time.isoformat(),
        "login_persistence": True
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["restored_sessions"] == 0
    assert metrics["rejected_restored_sessions"] == 1
    assert metrics["expired_sessions"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    # Expect 3 events: session_expiration, restored_session_rejection, and session_invalidation
    event_types = [e["event_type"] for e in events]
    assert "session_expiration" in event_types
    assert "restored_session_rejection" in event_types
    assert "session_invalidation" in event_types


def test_metrics_collection_on_restore_malformed(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that a malformed session file triggers malformed and rejection events."""
    temp_auth_file.write_text("not json payload", encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["malformed_session_files"] == 1
    assert metrics["rejected_restored_sessions"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    event_types = [e["event_type"] for e in events]
    assert "corrupted_persistence_file" in event_types
    assert "restored_session_rejection" in event_types
    assert "session_invalidation" in event_types


def test_metrics_collection_on_restore_unknown_user(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that an unknown user triggers unknown user and rejection events."""
    payload = {
        "user_id": "99999",  # Not in mock_registry
        "display_name": "Unknown",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "last_login": datetime.now(timezone.utc).isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["rejected_restored_sessions"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    event_types = [e["event_type"] for e in events]
    assert "unknown_user_rejection" in event_types
    assert "restored_session_rejection" in event_types


def test_metrics_collection_on_restore_locked_user(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that a locked user triggers locked user and rejection events."""
    payload = {
        "user_id": "00001",  # Locked is True in mock_registry
        "display_name": "Locked User",
        "role": "TRADER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "last_login": datetime.now(timezone.utc).isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["rejected_restored_sessions"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    event_types = [e["event_type"] for e in events]
    assert "locked_user_rejection" in event_types
    assert "restored_session_rejection" in event_types


def test_metrics_collection_on_restore_role_mismatch(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that role mismatch triggers role mismatch and rejection events."""
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "TRADER",  # Registry role is SUPER_USER
        "unit_code": "CORE",
        "home_branch": "HQ",
        "last_login": datetime.now(timezone.utc).isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["rejected_restored_sessions"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    event_types = [e["event_type"] for e in events]
    assert "role_mismatch_rejection" in event_types
    assert "restored_session_rejection" in event_types


def test_metrics_collection_on_restore_future_timestamp(temp_auth_file, temp_audit_file, mock_registry):
    """Verify that future-dated timestamp triggers future timestamp rejection."""
    future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "last_login": future_time.isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["rejected_restored_sessions"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    event_types = [e["event_type"] for e in events]
    assert "future_timestamp_rejection" in event_types
    assert "restored_session_rejection" in event_types


def test_interactive_login_metrics_and_audit(temp_audit_file, mock_registry):
    """Verify metrics and audit updates during successful and failed interactive logins."""
    # 1. Success
    user_ctx = auth.authenticate_credentials(mock_registry, "00000", "123456")
    assert user_ctx is not None
    
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["successful_interactive_logins"] == 1
    assert metrics["failed_interactive_logins"] == 0
    assert len(auth.AuthMetrics.authentication_latency_history) == 1
    assert metrics["avg_authentication_latency_seconds"] >= 0.0
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    assert events[-1]["event_type"] == "interactive_login_success"
    assert events[-1]["user_id"] == "00000"
    
    # 2. Failure (wrong password)
    with pytest.raises(auth.AuthFailure):
        auth.authenticate_credentials(mock_registry, "00000", "wrongpass")
        
    metrics = auth.AuthMetrics.get_metrics_dict()
    assert metrics["failed_interactive_logins"] == 1
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    assert events[-1]["event_type"] == "interactive_login_failure"


def test_secret_exclusion_in_audit_logs(temp_audit_file, mock_registry):
    """Verify that password, hashes, and secrets are absolutely excluded from audit events."""
    # Log with extra parameters mimicking passwords
    auth.record_auth_audit_event(
        "test_event",
        "00000",
        "SUCCESS",
        details={
            "password": "plain_password",
            "password_hash": "hash_value",
            "broker_key": "somekey",
            "pem_key": "pempayload",
            "safe_detail": "this is safe"
        }
    )
    
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    details = events[0]["details"]
    
    # Check that secrets are removed
    assert "safe_detail" in details
    assert "password" not in details
    assert "password_hash" not in details
    assert "broker_key" not in details
    assert "pem_key" not in details


def test_logout_audit_logging(temp_audit_file):
    """Verify logout audit events record auth_source and session age (AR-023 observability)."""
    # Avoid importing scripts.css_live_dashboard — module import runs full LIVE startup
    # and overwrites SESSION_USER_CTX, contaminating close_active_session patches.
    auth.record_auth_audit_event(
        "logout",
        "00000",
        "SUCCESS",
        failure_reason=None,
        session_age=3600.5,
        auth_source="interactive",
        details={"reason": "operator_exit"},
    )

    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    logout_event = next(e for e in events if e["event_type"] == "logout")
    assert logout_event["user_id"] == "00000"
    assert logout_event["details"]["auth_source"] == "interactive"
    assert logout_event["details"]["session_age_seconds"] >= 3600
    assert logout_event["details"]["outcome"] == "SUCCESS"


def test_dashboard_panel_output(capsys):
    """Verify that the operational status panel outputs correct statistics without errors."""
    mock_ctx = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "auth_source": "restored",
        "last_auth_time": "2026-07-13T20:00:00Z",
        "last_auth_event": "restored_session_success"
    }

    fixed_now = 1_700_000_000.0
    mock_status = {
        "created": fixed_now - 1800,  # 30 mins age
        "max_session_seconds": 86400
    }

    dash = _dashboard()
    with patch.object(dash, "SESSION_USER_CTX", mock_ctx), patch.object(
        dash.time, "time", return_value=fixed_now
    ):
        dash.print_authentication_status_panel(mock_status)

    captured = capsys.readouterr().out
    assert "--- OPERATIONAL AUTHENTICATION STATUS ---" in captured
    assert "Auth State: AUTHENTICATED" in captured
    assert "Auth Source: restored" in captured
    assert "Session Age: 1800 seconds" in captured
    assert "Last Auth Time: 2026-07-13T20:00:00Z" in captured
    assert "Last Auth Event: restored_session_success" in captured
    assert "Session Expiry Countdown: 84600 seconds" in captured
