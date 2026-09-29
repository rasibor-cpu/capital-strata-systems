"""UAT finding: POST /auth/operator/change-password bypassed the disable and lockout controls.

``css_sign_on.change_authenticated_password`` checked only the current
password, and the operator API then issued a brand-new session. So a disabled
operator who knew their password could get a fresh session, and the endpoint
was an unthrottled password-guessing oracle that sidestepped sign-in's
three-attempt lockout. It now shares sign-in's exact disabled / lockout /
failed-attempt policy.
"""
from __future__ import annotations

import pytest

import backend.app.auth.auth_audit as auth_audit
import backend.app.auth.token_store as token_store_module
from dashboard.auth import css_sign_on
from engine.commercial.commercial_audit import CommercialAuditLog
from tests.test_operator_authentication import operator_env  # noqa: F401  (fixture)

NEW = "Fincon-Rotated-Pass-7!"


def _change(client, current, new=NEW, user_id="20001"):
    return client.post("/auth/operator/change-password", json={
        "user_id": user_id, "current_password": current, "new_password": new, "confirm_password": new,
    })


def _sessions_for(user_id):
    return [t for t, info in token_store_module.token_store._sessions.items() if info.username == user_id]


def test_disabled_operator_cannot_obtain_a_session_via_change_password(operator_env):  # noqa: F811
    users = css_sign_on.load_users()
    css_sign_on.set_user_disabled(users, {"user_id": "20005", "role": "SUPER_USER"}, "20001", True)
    css_sign_on.save_users(users)

    resp = _change(operator_env, "fincon-pass-1")
    assert resp.status_code == 401
    assert "disabled" in resp.json()["detail"].lower()
    assert _sessions_for("20001") == []
    # The password was not changed either.
    assert css_sign_on.verify_password("fincon-pass-1", css_sign_on.load_users()["20001"]["password_hash"])


def test_wrong_current_password_counts_toward_lockout(operator_env):  # noqa: F811
    for _ in range(2):
        assert _change(operator_env, "wrong-guess").status_code == 401
    third = _change(operator_env, "wrong-guess")
    assert third.status_code == 401
    assert "paused" in third.json()["detail"]
    # Locked: even the right password is refused now, on both entry points.
    assert _change(operator_env, "fincon-pass-1").status_code == 401
    login = operator_env.post("/auth/operator/login", json={"user_id": "20001", "password": "fincon-pass-1"})
    assert login.status_code == 401 and "paused" in login.json()["detail"]
    assert _sessions_for("20001") == []


def test_login_and_change_password_share_one_failed_attempt_counter(operator_env):  # noqa: F811
    for _ in range(2):
        operator_env.post("/auth/operator/login", json={"user_id": "20001", "password": "wrong-guess"})
    locked = _change(operator_env, "wrong-guess")
    assert locked.status_code == 401 and "paused" in locked.json()["detail"]


def test_successful_change_still_works_and_resets_the_counter(operator_env):  # noqa: F811
    assert _change(operator_env, "wrong-guess").status_code == 401
    ok = _change(operator_env, "fincon-pass-1")
    assert ok.status_code == 200 and ok.json()["token"]
    assert css_sign_on.load_users()["20001"]["failed_attempts"] == 0


def test_change_password_failures_are_audited_without_secrets(operator_env, tmp_path, monkeypatch):  # noqa: F811
    db = str(tmp_path / "auth.sqlite3")
    monkeypatch.setenv("CSS_AUTH_AUDIT_DB", db)
    for _ in range(3):
        _change(operator_env, "wrong-guess-secret")
    events = CommercialAuditLog(db).events(object_type="operator_auth")
    outcomes = [(e.action, e.outcome) for e in events]
    assert outcomes == [("LOGIN_FAILURE", "WRONG_PASSWORD"), ("LOGIN_FAILURE", "WRONG_PASSWORD"),
                        ("ACCOUNT_LOCKOUT", "LOCKED")]
    assert "wrong-guess-secret" not in repr(events)
