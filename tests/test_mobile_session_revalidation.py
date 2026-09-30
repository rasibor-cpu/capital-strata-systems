"""Register item #14: mobile sessions honour account disable / password change / role change.

The mobile app's session store is separate from ``token_store``. Before
COM-015, disabling an operator or changing their password through the operator
API revoked only token_store sessions, so an already-open mobile session kept
working (including /controls and /trade) until it aged out. Mobile sessions are
now re-validated against the shared user store on every request.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import dashboard.auth.css_sign_on as css_sign_on
from dashboard.mobile import mobile_app
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_mobile_csrf import CONTROLS_BODY, SUPER_USER_CTX, VIEWER_CTX, seed_mobile_users
from tests.test_operator_authentication import operator_env  # noqa: F401  (fixture)


@pytest.fixture
def mobile(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(users_file))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, users_file))
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    seed_mobile_users(users_file, SUPER_USER_CTX, VIEWER_CTX)
    mobile_app._SESSIONS.clear()
    client = TestClient(mobile_app.app)
    client.users_file = users_file
    yield client
    mobile_app._SESSIONS.clear()


def _cookie(token):
    return {"Cookie": f"{mobile_app.SESSION_COOKIE}={token}"}


def _edit_user(users_file, user_id, **changes):
    users = css_sign_on.load_users(users_file)
    if changes.pop("_delete", False):
        users.pop(user_id)
    else:
        users[user_id].update(changes)
    css_sign_on.save_users(users, users_file)


def test_a_valid_session_keeps_working_across_requests(mobile):
    token = mobile_app._create_session(VIEWER_CTX)
    for _ in range(3):
        assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 200


@pytest.mark.parametrize("change", [
    {"disabled": True},
    {"role": "SUPER_USER"},           # privilege changed since login: re-authenticate
    {"_delete": True},
    {"last_password_change": "FUTURE"},
    {"last_password_change": "not-a-timestamp"},
])
def test_session_dies_when_the_account_changes_underneath_it(mobile, change):
    token = mobile_app._create_session(VIEWER_CTX)
    assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 200
    if change.get("last_password_change") == "FUTURE":
        change = {"last_password_change": (datetime.now() + timedelta(seconds=5)).isoformat(timespec="seconds")}
    _edit_user(mobile.users_file, VIEWER_CTX["user_id"], **change)

    resp = mobile.get("/dashboard", headers=_cookie(token))
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    assert token not in mobile_app._SESSIONS  # revoked, not merely refused once


def test_disabled_super_user_cannot_use_an_open_session_to_change_controls(mobile, tmp_path):
    token = mobile_app._create_session(SUPER_USER_CTX)
    csrf = mobile_app._SESSIONS[token]["csrf_token"]
    _edit_user(mobile.users_file, SUPER_USER_CTX["user_id"], disabled=True)

    resp = mobile.post("/controls", data={**CONTROLS_BODY, "csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    assert not (tmp_path / "controls.json").exists()  # the control change never ran


def test_unreadable_user_store_fails_closed(mobile, monkeypatch):
    token = mobile_app._create_session(VIEWER_CTX)

    def _broken(*_a, **_k):
        raise RuntimeError("CSS_USER_STORE_UNREADABLE")

    monkeypatch.setattr(mobile_app, "load_users", _broken)
    assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 303


def test_operator_api_disable_ends_an_open_mobile_session(operator_env, monkeypatch):  # noqa: F811
    # Real cross-channel flow: FINCON 20001 is signed in on mobile; a super
    # user disables the account through the operator API.
    monkeypatch.setattr(mobile_app, "load_users", css_sign_on.load_users)  # operator_env's temp store
    mobile_app._SESSIONS.clear()
    fincon_ctx = {"user_id": "20001", "display_name": "Test FinCon", "role": "FINCON",
                  "unit_code": "CORE", "home_branch": "HQ"}
    token = mobile_app._create_session(fincon_ctx)
    mobile = TestClient(mobile_app.app)
    assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 200

    su = operator_env.post("/auth/operator/login", json={"user_id": "20005", "password": "superuser-pass-1"}).json()
    resp = operator_env.post("/auth/operator/admin/users/20001/disable", headers={"Authorization": f"Bearer {su['token']}"})
    assert resp.status_code == 200

    assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 303
    assert token not in mobile_app._SESSIONS
    mobile_app._SESSIONS.clear()


def test_operator_api_password_change_ends_an_open_mobile_session(operator_env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(mobile_app, "load_users", css_sign_on.load_users)
    mobile_app._SESSIONS.clear()
    fincon_ctx = {"user_id": "20001", "display_name": "Test FinCon", "role": "FINCON",
                  "unit_code": "CORE", "home_branch": "HQ"}
    users = css_sign_on.load_users()
    users["20001"]["last_password_change"] = "2026-01-01T00:00:00"
    css_sign_on.save_users(users)
    token = mobile_app._create_session(fincon_ctx)
    mobile_app._SESSIONS[token]["created"] -= 5  # issued clearly before the change below
    mobile = TestClient(mobile_app.app)
    assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 200

    resp = operator_env.post("/auth/operator/change-password", json={
        "user_id": "20001", "current_password": "fincon-pass-1",
        "new_password": "Fincon-Changed-Pass-9!", "confirm_password": "Fincon-Changed-Pass-9!",
    })
    assert resp.status_code == 200, resp.content

    assert mobile.get("/dashboard", headers=_cookie(token)).status_code == 303
    mobile_app._SESSIONS.clear()


@pytest.mark.parametrize("css_env,secure", [(None, True), ("production", True), ("development", False)])
def test_mobile_session_cookie_is_secure_unless_explicitly_development(mobile, monkeypatch, css_env, secure):
    if css_env is None:
        monkeypatch.delenv("CSS_ENV", raising=False)
    else:
        monkeypatch.setenv("CSS_ENV", css_env)
    _edit_user(mobile.users_file, VIEWER_CTX["user_id"], last_password_change=datetime.now().isoformat(timespec="seconds"))
    resp = mobile.post("/login", data={"user_id": VIEWER_CTX["user_id"], "password": "seeded-pass-1"})
    assert resp.status_code == 303, resp.content
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{mobile_app.SESSION_COOKIE}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert ("Secure" in cookie) is secure
