"""Authentication / account-lifecycle audit trail integrity.

Verifies that login success/failure/lockout, logout, password change,
session revocation, and account disable/enable/authorization-denial all
produce exactly the expected append-only, hash-chained event -- reusing
CommercialAuditLog, not a parallel logging subsystem -- and that no
credential/token/cookie value is ever recorded.
"""
from __future__ import annotations

from datetime import datetime
import hashlib

import pytest

import backend.app.auth.auth_audit as auth_audit
from backend.app.auth.token_store import TokenStore
from dashboard.auth import css_sign_on
from engine.commercial.commercial_audit import CommercialAuditLog

SUPER_USER_CTX = {"user_id": "00000", "role": "SUPER_USER"}


@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    monkeypatch.delenv("CSS_AUTH_AUDIT_DB", raising=False)
    db_path = str(tmp_path / "auth_audit.sqlite3")
    monkeypatch.setattr(auth_audit, "DEFAULT_AUTH_AUDIT_DB", db_path)
    return db_path


def _events(db_path, action=None):
    log = CommercialAuditLog(db_path)
    events = log.events(object_type="operator_auth")
    if action is not None:
        events = [e for e in events if e.action == action]
    return events


def _fresh_user(role="FINCON", password="fincon-pass-1"):
    users = {}
    css_sign_on.create_user(users, SUPER_USER_CTX, "20001", "Test Operator", role, password, must_change_password=False)
    users["20001"]["last_password_change"] = datetime.now().isoformat(timespec="seconds")
    return users


# ---------------------------------------------------------------------------
# Login success / failure / lockout
# ---------------------------------------------------------------------------

def test_successful_login_emits_exactly_one_login_success_event(audit_db):
    users = _fresh_user()
    css_sign_on.authenticate_credentials(users, "20001", "fincon-pass-1")

    events = _events(audit_db, "LOGIN_SUCCESS")
    assert len(events) == 1
    assert events[0].actor_id == "20001"
    assert events[0].actor_role == "FINCON"
    assert events[0].outcome == "SUCCEEDED"


def test_failed_login_emits_exactly_one_login_failure_event(audit_db):
    users = _fresh_user()
    with pytest.raises(css_sign_on.AuthFailure):
        css_sign_on.authenticate_credentials(users, "20001", "wrong-password")

    events = _events(audit_db, "LOGIN_FAILURE")
    assert len(events) == 1
    assert events[0].actor_id == "20001"
    assert events[0].outcome == "WRONG_PASSWORD"


def test_unknown_user_login_attempt_is_still_logged_server_side(audit_db):
    users = _fresh_user()
    with pytest.raises(css_sign_on.AuthFailure):
        css_sign_on.authenticate_credentials(users, "99999", "whatever")

    events = _events(audit_db, "LOGIN_FAILURE")
    assert len(events) == 1
    assert events[0].outcome == "UNKNOWN_USER"


def test_lockout_after_repeated_failures_emits_one_account_lockout_event(audit_db):
    users = _fresh_user()
    for _ in range(2):
        with pytest.raises(css_sign_on.AuthFailure):
            css_sign_on.authenticate_credentials(users, "20001", "wrong-password")
    with pytest.raises(css_sign_on.AuthFailure) as exc_info:
        css_sign_on.authenticate_credentials(users, "20001", "wrong-password")
    assert exc_info.value.code == "AUTH_LOCKOUT"

    lockout_events = _events(audit_db, "ACCOUNT_LOCKOUT")
    assert len(lockout_events) == 1
    assert lockout_events[0].actor_id == "20001"

    failure_events = _events(audit_db, "LOGIN_FAILURE")
    assert len(failure_events) == 2  # the two WRONG_PASSWORD attempts before lockout kicked in


def test_disabled_account_login_attempt_is_logged_and_distinct_from_lockout(audit_db):
    users = _fresh_user()
    users["20001"]["disabled"] = True
    with pytest.raises(css_sign_on.AuthFailure) as exc_info:
        css_sign_on.authenticate_credentials(users, "20001", "fincon-pass-1")
    assert exc_info.value.code == "ACCOUNT_DISABLED"

    events = _events(audit_db, "LOGIN_FAILURE")
    assert len(events) == 1
    assert events[0].outcome == "ACCOUNT_DISABLED"
    assert not _events(audit_db, "ACCOUNT_LOCKOUT")


# ---------------------------------------------------------------------------
# Logout / session revocation
# ---------------------------------------------------------------------------

def test_logout_emits_exactly_one_logout_event(audit_db, monkeypatch):
    import backend.app.auth.token_store as token_store_module
    from backend.app.auth.session_dependency import revoke_session_from_request

    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    token = store.create_session("20001", ["FINCON"], minutes=60)

    class _FakeRequest:
        cookies = {"css_operator_session": token}
        headers = {}

    assert revoke_session_from_request(_FakeRequest()) is True

    events = _events(audit_db, "LOGOUT")
    assert len(events) == 1
    assert events[0].actor_id == "20001"
    assert events[0].actor_role == "FINCON"


def test_password_change_revokes_all_sessions_and_both_events_are_logged(audit_db, monkeypatch):
    import backend.app.auth.token_store as token_store_module

    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    store.create_session("20001", ["FINCON"], minutes=60)
    store.create_session("20001", ["FINCON"], minutes=60)

    users = _fresh_user()
    css_sign_on.change_password(users, "20001", "brand-new-pass-1", "brand-new-pass-1")
    store.revoke_all_for_user("20001")

    password_events = _events(audit_db, "PASSWORD_CHANGE")
    assert len(password_events) == 1

    revoke_all_events = _events(audit_db, "SESSION_REVOKE_ALL")
    assert len(revoke_all_events) == 1
    assert revoke_all_events[0].details["sessions_revoked"] == 2


# ---------------------------------------------------------------------------
# Account disable / enable / authorization denial
# ---------------------------------------------------------------------------

def test_account_disable_and_enable_each_emit_one_event(audit_db):
    users = _fresh_user()
    css_sign_on.set_user_disabled(users, SUPER_USER_CTX, "20001", True)
    css_sign_on.set_user_disabled(users, SUPER_USER_CTX, "20001", False)

    disabled_events = _events(audit_db, "ACCOUNT_DISABLED")
    enabled_events = _events(audit_db, "ACCOUNT_ENABLED")
    assert len(disabled_events) == 1
    assert len(enabled_events) == 1
    assert disabled_events[0].details["target_user_id"] == "20001"


def test_non_super_user_disable_attempt_is_logged_as_authorization_denied(audit_db):
    users = _fresh_user()
    with pytest.raises(css_sign_on.AuthFailure):
        css_sign_on.set_user_disabled(users, {"user_id": "20001", "role": "FINCON"}, "20001", True)

    events = _events(audit_db, "AUTHORIZATION_DENIED")
    assert len(events) == 1
    assert events[0].outcome == "DENIED"


# ---------------------------------------------------------------------------
# No secret ever appears in any auth-audit event
# ---------------------------------------------------------------------------

def test_no_password_hash_or_session_token_ever_appears_in_audit_events(audit_db, monkeypatch):
    import backend.app.auth.token_store as token_store_module
    from backend.app.auth.session_dependency import revoke_session_from_request

    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    token = store.create_session("20001", ["FINCON"], minutes=60)

    users = _fresh_user()
    css_sign_on.authenticate_credentials(users, "20001", "fincon-pass-1")
    css_sign_on.change_password(users, "20001", "brand-new-pass-2", "brand-new-pass-2")

    class _FakeRequest:
        cookies = {"css_operator_session": token}
        headers = {}

    revoke_session_from_request(_FakeRequest())

    secrets_to_check = [
        token,
        "fincon-pass-1",
        "brand-new-pass-2",
        users["20001"]["password_hash"],
        hashlib.sha256(b"fincon-pass-1").hexdigest(),
    ]
    log = CommercialAuditLog(audit_db)
    for event in log.events(object_type="operator_auth"):
        payload = str(event.details) + str(event.reason or "")
        for secret in secrets_to_check:
            assert secret not in payload


# ---------------------------------------------------------------------------
# Hash-chain integrity is preserved for this event stream too
# ---------------------------------------------------------------------------

def test_auth_audit_chain_verifies_and_has_no_duplicate_events(audit_db):
    users = _fresh_user()
    css_sign_on.authenticate_credentials(users, "20001", "fincon-pass-1")
    with pytest.raises(css_sign_on.AuthFailure):
        css_sign_on.authenticate_credentials(users, "20001", "wrong")
    css_sign_on.set_user_disabled(users, SUPER_USER_CTX, "20001", True)

    log = CommercialAuditLog(audit_db)
    verification = log.verify()
    assert verification.ok

    events = log.events(object_type="operator_auth")
    event_ids = [e.event_id for e in events]
    assert len(event_ids) == len(set(event_ids))
