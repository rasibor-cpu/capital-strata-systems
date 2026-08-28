import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dashboard.auth import css_sign_on as auth

pytestmark = pytest.mark.live_session


@pytest.fixture(autouse=True)
def _disable_automated_auth_bypass(monkeypatch):
    """Persistence restoration must exercise real restore/console paths (AR-023)."""
    monkeypatch.delenv("CSS_AUTOMATED_INPUT", raising=False)
    monkeypatch.delenv("CSS_AUTH_TEST_PROFILE", raising=False)
    monkeypatch.delenv("CSS_AUTH_UI", raising=False)


@pytest.fixture
def temp_auth_file(tmp_path):
    """Fixture to mock the SESSION_AUTH_FILE with a temporary file."""
    mock_file = tmp_path / "css_auth_session.json"
    with patch.object(auth, "SESSION_AUTH_FILE", mock_file):
        yield mock_file
    # Cleanup after test
    try:
        if mock_file.exists():
            mock_file.unlink()
    except Exception:
        pass


@pytest.fixture
def mock_registry():
    """Mock user registry database."""
    return {
        "00000": {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "locked": False,
            "lockout_until": None,
        },
        "00001": {
            "user_id": "00001",
            "display_name": "Viewer Test",
            "role": "VIEWER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "locked": False,
            "lockout_until": None,
        },
        "00002": {
            "user_id": "00002",
            "display_name": "Trader Test",
            "role": "TRADER",
            "unit_code": "CORE",
            "home_branch": "HQ",
            "locked": True,
            "lockout_until": None,
        }
    }


def test_missing_persistence_file(temp_auth_file, mock_registry):
    """1. Verify that when SESSION_AUTH_FILE does not exist, restore_login_session() returns None."""
    assert not temp_auth_file.exists()
    result = auth.restore_login_session(mock_registry)
    assert result is None


def test_valid_session_restoration(temp_auth_file, mock_registry):
    """2. Verify that a valid session file successfully restores and returns the correct context."""
    valid_payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "login_persistence": True
    }
    temp_auth_file.write_text(json.dumps(valid_payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is not None
    assert result["user_id"] == "00000"
    assert result["role"] == "SUPER_USER"
    assert result["display_name"] == "CSS Administrator"


def test_malformed_json(temp_auth_file, mock_registry):
    """3. Verify that if the file contains invalid JSON, it is invalidated and returns None without crashing."""
    temp_auth_file.write_text("{malformed json", encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()  # Invalidated/deleted


def test_json_root_not_object(temp_auth_file, mock_registry):
    """4. Verify that if the file contains a JSON list or primitive (not a dict), it returns None and is deleted."""
    temp_auth_file.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_missing_required_fields(temp_auth_file, mock_registry):
    """5. Verify that if a required field is missing, it returns None and is deleted."""
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        # unit_code is missing
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_wrong_field_types(temp_auth_file, mock_registry):
    """6. Verify that if any field has an invalid type, it returns None and is deleted."""
    payload = {
        "user_id": 12345,  # int instead of str
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_unknown_user(temp_auth_file, mock_registry):
    """7. Verify that if the user_id is not in the user registry, it returns None and is deleted."""
    payload = {
        "user_id": "99999",  # Unknown
        "display_name": "Unknown User",
        "role": "VIEWER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_locked_out_user(temp_auth_file, mock_registry):
    """8. Verify that if the user is locked out, it returns None and is deleted."""
    # User 00002 has locked: True
    payload = {
        "user_id": "00002",
        "display_name": "Trader Test",
        "role": "TRADER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_expired_session(temp_auth_file, mock_registry):
    """9. Verify that if the session was created > 24 hours ago, it is invalidated and returns None."""
    expired_time = datetime.now(timezone.utc) - timedelta(hours=25)
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "expired-session-id",
        "last_login": expired_time.isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_malformed_timestamp(temp_auth_file, mock_registry):
    """10. Verify that if last_login is not a valid ISO datetime format, it returns None and is deleted."""
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "invalid-ts-session-id",
        "last_login": "invalid-timestamp",
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_future_dated_session(temp_auth_file, mock_registry):
    """11. Verify that if last_login is materially in the future (> 60 seconds), it returns None and is deleted."""
    future_time = datetime.now(timezone.utc) + timedelta(seconds=120)
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "future-session-id",
        "last_login": future_time.isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_role_mismatch(temp_auth_file, mock_registry):
    """12. Verify that if the persisted role differs from registry, it returns None and is deleted."""
    payload = {
        "user_id": "00001",  # Registry role is VIEWER
        "display_name": "Viewer Test",
        "role": "SUPER_USER",  # Persisted role mismatch!
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_permissions_are_derived_canonically(temp_auth_file, mock_registry):
    """13. Verify that role and permissions context values are constructed from user registry."""
    payload = {
        "user_id": "00001",
        "display_name": "Persisted Manipulated Display Name",  # Will use registry/persisted context safely
        "role": "VIEWER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is not None
    # Context should map cleanly
    assert result["role"] == "VIEWER"


def test_no_password_stored(temp_auth_file, mock_registry):
    """14. Verify that the generated/saved session file does not contain a password field."""
    valid_payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
    }
    
    # Save a session
    auth.persist_login_session(valid_payload)
    
    # Reload and verify
    raw = temp_auth_file.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert "password" not in data
    assert "password_hash" not in data


def test_no_broker_credentials_restored(temp_auth_file, mock_registry):
    """15. Verify that no broker credentials, keys, or PEM context are present in the returned context."""
    valid_payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "test-session-id",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(valid_payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is not None
    # Must not contain credentials
    for key in result:
        assert "key" not in key.lower()
        assert "secret" not in key.lower()
        assert "pem" not in key.lower()
        assert "password" not in key.lower()


@patch("dashboard.auth.css_sign_on.load_users")
def test_valid_restoration_readiness(mock_load, temp_auth_file, mock_registry, monkeypatch):
    """16. Verify explicit session restore policy returns restored context."""
    mock_load.return_value = mock_registry
    monkeypatch.setenv("CSS_AUTH_ALLOW_SESSION_RESTORE", "1")
    
    valid_payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "restore-session-001",
        "last_login": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    temp_auth_file.write_text(json.dumps(valid_payload), encoding="utf-8")
    
    result = auth.await_login_ready_state()
    assert result is not None
    assert result["user_id"] == "00000"
    assert result["role"] == "SUPER_USER"
    assert result["auth_provenance"] == auth.AUTH_PROVENANCE_SESSION_RESUME


def test_invalid_restoration_falls_through(monkeypatch, temp_auth_file, mock_registry):
    """17. Verify that if the persistence file is invalid, it falls through to console/gui login."""
    mock_load = MagicMock(return_value=mock_registry)
    mock_console = MagicMock(return_value={"user_id": "00000", "role": "SUPER_USER"})
    monkeypatch.setattr(auth, "load_users", mock_load)
    monkeypatch.setattr(auth, "await_console_login", mock_console)
    
    # Set UI override to cli for this test only.
    monkeypatch.setenv("CSS_AUTH_UI", "cli")
    monkeypatch.setenv("CSS_AUTH_ALLOW_SESSION_RESTORE", "1")
    
    # Save an invalid (expired) session file
    expired_time = datetime.now(timezone.utc) - timedelta(hours=30)
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "expired-session-id",
        "last_login": expired_time.isoformat(),
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.await_login_ready_state()
    assert result == {"user_id": "00000", "role": "SUPER_USER"}
    mock_load.assert_called_once()
    mock_console.assert_called_once_with(mock_registry)
    assert not temp_auth_file.exists()  # Should be invalidated/deleted


def test_logout_invalidation(temp_auth_file):
    """18. Verify that invalidate_login_session removes the persisted session file."""
    temp_auth_file.write_text("some session data", encoding="utf-8")
    assert temp_auth_file.exists()
    
    auth.invalidate_login_session()
    assert not temp_auth_file.exists()


@patch("dashboard.auth.css_sign_on.load_users")
def test_corrupted_session_does_not_crash_startup(mock_load, temp_auth_file, mock_registry):
    """19. Verify that corrupted file content does not throw unhandled exception and cleanly falls back."""
    mock_load.return_value = mock_registry
    temp_auth_file.write_text("random bad binary content or corruption", encoding="utf-8")
    
    # Try restoring
    result = auth.restore_login_session(mock_registry)
    assert result is None
    assert not temp_auth_file.exists()


def test_backward_compatibility_naive_timestamp(temp_auth_file, mock_registry):
    """20. Verify backward compatibility: naive datetime string in last_login is parsed as UTC."""
    naive_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()  # timezone-naive
    payload = {
        "user_id": "00000",
        "display_name": "CSS Administrator",
        "role": "SUPER_USER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "auth_session_id": "naive-session-id",
        "last_login": naive_str,
    }
    temp_auth_file.write_text(json.dumps(payload), encoding="utf-8")
    
    result = auth.restore_login_session(mock_registry)
    assert result is not None
    assert result["user_id"] == "00000"
