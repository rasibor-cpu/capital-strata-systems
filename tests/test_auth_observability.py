import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock stdin and set test mode before dashboard loads
os.environ["CSS_AUTOMATED_INPUT"] = "1"
os.environ["CSS_TEST_MODE"] = "1"
sys.modules["builtins"].input = lambda prompt: "1"

from backend.security.audit_ledger import AuditLedger
from dashboard.auth import css_sign_on as auth
from scripts import css_live_dashboard as dashboard


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset AuthMetrics between tests."""
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
    
    # We patch BOTH get_audit_ledger() return value and the internal audit_file parameter
    ledger_instance = AuditLedger()
    ledger_instance.audit_file = mock_file
    
    with patch("dashboard.auth.css_sign_on.get_audit_ledger", return_value=ledger_instance):
        with patch("scripts.css_live_dashboard.audit_ledger", ledger_instance):
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
    assert metrics["avg_authentication_latency_seconds"] > 0
    
    # Check audit log
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    assert len(events) == 1
    assert events[0]["event_type"] == "restored_session_success"
    assert events[0]["user_id"] == "00000"
    assert events[0]["details"]["outcome"] == "SUCCESS"


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
    assert metrics["avg_authentication_latency_seconds"] > 0
    
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
    """Verify that closing a session logs a logout event with accurate session age."""
    # Set mock context
    mock_ctx = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "session_created": time.time() - 3600,  # 1 hour ago
        "auth_source": "interactive"
    }
    
    with patch("scripts.css_live_dashboard.SESSION_USER_CTX", mock_ctx):
        with patch("scripts.css_live_dashboard.SESSION_CLOSED", False):
            # Run logout
            dashboard.close_active_session("operator_exit")
            
    events = [json.loads(line) for line in temp_audit_file.read_text().splitlines()]
    logout_event = None
    for e in events:
        if e["event_type"] == "logout":
            logout_event = e
            break
            
    assert logout_event is not None
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
    
    mock_status = {
        "created": time.time() - 1800,  # 30 mins age
        "max_session_seconds": 86400
    }
    
    with patch("scripts.css_live_dashboard.SESSION_USER_CTX", mock_ctx):
        dashboard.print_authentication_status_panel(mock_status)
        
    captured = capsys.readouterr().out
    assert "--- OPERATIONAL AUTHENTICATION STATUS ---" in captured
    assert "Auth State: AUTHENTICATED" in captured
    assert "Auth Source: restored" in captured
    assert "Session Age: 1800 seconds" in captured
    assert "Last Auth Time: 2026-07-13T20:00:00Z" in captured
    assert "Last Auth Event: restored_session_success" in captured
    assert "Session Expiry Countdown: 84600 seconds" in captured
