"""CSRF protection for dashboard/mobile/mobile_app.py's cookie-authenticated,
state-changing routes.

Audited mutating, cookie-authenticated routes in mobile_app.py:
  POST /controls          -- change system-wide trading controls (can arm live trading)
  POST /trade              -- submit a trade ticket
  POST /users               -- create an operator account
  POST /password-change     -- set a new password (forced first-login flow;
                               authenticated by a short-lived possession cookie,
                               not the main session, but still a full
                               account-takeover primitive if forgeable)
  POST /logout              -- revoke the session (state-changing, but the worst
                               outcome is forcing a logout -- deliberately left
                               on SameSite=Lax alone, same reasoning already
                               applied to the web dashboard's /logout in COM-012/013)
  POST /login               -- the auth action itself; no session exists yet to
                               protect, so classic CSRF does not apply

This suite covers the four given a synchronizer CSRF token (session-bound,
rotates with the session, dies with it): /controls, /trade, /users,
/password-change.
"""
from __future__ import annotations

import pytest

from dashboard.mobile import mobile_app
from tests.asgi_test_client import AsgiTestClient as TestClient

SUPER_USER_CTX = {
    "user_id": "99999",
    "display_name": "Test Super User",
    "role": "SUPER_USER",
    "unit_code": "CORE",
    "home_branch": "HQ",
}
VIEWER_CTX = {
    "user_id": "88888",
    "display_name": "Test Viewer",
    "role": "VIEWER",
    "unit_code": "CORE",
    "home_branch": "HQ",
}


@pytest.fixture(autouse=True)
def clean_sessions():
    mobile_app._SESSIONS.clear()
    mobile_app._PASSWORD_CHANGES.clear()
    yield
    mobile_app._SESSIONS.clear()
    mobile_app._PASSWORD_CHANGES.clear()


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    # /users mutates the operator user store -- never let a test touch the
    # real data/users.json, even indirectly via a CSRF-accepted request.
    import dashboard.auth.css_sign_on as css_sign_on

    users_file = tmp_path / "users.json"
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(users_file))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, users_file))
    return TestClient(mobile_app.app)


def _seed_session(user_ctx):
    token = mobile_app._create_session(user_ctx)
    csrf = mobile_app._SESSIONS[token]["csrf_token"]
    return token, csrf


def _cookie(token):
    return {"Cookie": f"{mobile_app.SESSION_COOKIE}={token}"}


CONTROLS_BODY = {"mobile_trading_mode": "MOBILE_READ_ONLY", "live_order_kill_switch": "off", "engine_mode": "SAFE"}
TRADE_BODY = {"mode": "MOBILE_PAPER_TRADING", "broker": "CSS_PAPER", "asset_class": "CRYPTO",
              "symbol": "BTC-USD", "side": "BUY", "amount": "1.00", "qty": "1"}
USERS_BODY = {"user_id": "12345", "display_name": "New Op", "role": "VIEWER",
              "initial_password": "brand-new-pw-1", "unit_code": "CORE", "home_branch": "HQ"}

MUTATING_ROUTES = [
    ("/controls", CONTROLS_BODY),
    ("/trade", TRADE_BODY),
    ("/users", USERS_BODY),
]


# ---------------------------------------------------------------------------
# Core negative matrix, parametrized across all three session-gated mutating routes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_anonymous_request_is_rejected(client, path, body):
    resp = client.post(path, data=body)
    assert resp.status_code == 303  # redirected to /login, not executed
    assert resp.headers.get("location") == "/login"


@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_cookie_without_csrf_token_is_rejected(client, path, body):
    token, _csrf = _seed_session(SUPER_USER_CTX)
    resp = client.post(path, data=body, headers=_cookie(token))
    assert resp.status_code == 403


@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_invalid_csrf_token_is_rejected(client, path, body):
    token, _csrf = _seed_session(SUPER_USER_CTX)
    resp = client.post(path, data={**body, "csrf_token": "not-the-real-token"}, headers=_cookie(token))
    assert resp.status_code == 403


@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_csrf_token_from_another_session_is_rejected(client, path, body):
    token_a, _csrf_a = _seed_session(SUPER_USER_CTX)
    _token_b, csrf_b = _seed_session(dict(SUPER_USER_CTX, user_id="77777"))
    resp = client.post(path, data={**body, "csrf_token": csrf_b}, headers=_cookie(token_a))
    assert resp.status_code == 403


@pytest.mark.parametrize("path,body", [("/controls", CONTROLS_BODY), ("/users", USERS_BODY)])
def test_valid_csrf_token_without_required_role_is_rejected(client, path, body):
    token, csrf = _seed_session(VIEWER_CTX)
    resp = client.post(path, data={**body, "csrf_token": csrf}, headers=_cookie(token))
    # Role/permission denial, not a CSRF failure -- both happen to be 403,
    # but this proves CSRF is checked independently of, not as a substitute
    # for, the role/permission gate (a matching CSRF token alone is not enough).
    assert resp.status_code == 403


def test_valid_csrf_token_without_trade_authority_is_denied_in_the_result_not_by_http_status(client):
    # /trade's authorization model predates this work: it always returns 200
    # and reports denial inside the rendered result payload (status code
    # "MOBILE_AUTHORITY_DENIED"), rather than an HTTP 403 -- CSRF passing
    # correctly gets the request to that pre-existing authorization check
    # without granting the trade itself.
    token, csrf = _seed_session(VIEWER_CTX)
    resp = client.post("/trade", data={**TRADE_BODY, "csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 200
    assert "Trading authority denied" in resp.content.decode("utf-8", errors="replace")


@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_expired_session_with_valid_looking_token_is_rejected(client, path, body):
    token, csrf = _seed_session(SUPER_USER_CTX)
    mobile_app._SESSIONS[token]["created"] = 0.0  # far enough in the past to have expired
    resp = client.post(path, data={**body, "csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/login"


@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_revoked_session_with_token_is_rejected(client, path, body):
    token, csrf = _seed_session(SUPER_USER_CTX)
    mobile_app._SESSIONS.pop(token, None)  # simulate logout
    resp = client.post(path, data={**body, "csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/login"


@pytest.mark.parametrize("path,body", MUTATING_ROUTES)
def test_valid_authorized_session_with_matching_csrf_is_accepted(client, path, body):
    token, csrf = _seed_session(SUPER_USER_CTX)
    resp = client.post(path, data={**body, "csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Session-lifecycle interactions: a token must die with its session
# ---------------------------------------------------------------------------

def test_csrf_token_replay_after_logout_is_rejected(client):
    token, csrf = _seed_session(SUPER_USER_CTX)
    logout_resp = client.post("/logout", headers=_cookie(token))
    assert logout_resp.status_code == 303
    assert token not in mobile_app._SESSIONS

    replay = client.post("/controls", data={**CONTROLS_BODY, "csrf_token": csrf}, headers=_cookie(token))
    assert replay.status_code == 303  # session gone -> bounced to /login, action never runs


def test_new_login_rotates_the_csrf_token(client, monkeypatch, tmp_path):
    import dashboard.auth.css_sign_on as css_sign_on
    from datetime import datetime

    users_file = tmp_path / "users.json"
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(users_file))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, users_file))

    users = real_load(users_file)
    css_sign_on.create_user(
        users, {"user_id": "00000", "role": "SUPER_USER"}, "40001", "Rotator", "SUPER_USER",
        "rotate-pass-1", must_change_password=False,
    )
    users["40001"]["last_password_change"] = datetime.now().isoformat(timespec="seconds")
    real_save(users, users_file)

    first = client.post("/login", data={"user_id": "40001", "password": "rotate-pass-1"})
    first_cookie = first.headers.get("set-cookie", "")
    first_token = first_cookie.split(f"{mobile_app.SESSION_COOKIE}=", 1)[1].split(";", 1)[0]
    first_csrf = mobile_app._SESSIONS[first_token]["csrf_token"]

    second = client.post("/login", data={"user_id": "40001", "password": "rotate-pass-1"})
    second_cookie = second.headers.get("set-cookie", "")
    second_token = second_cookie.split(f"{mobile_app.SESSION_COOKIE}=", 1)[1].split(";", 1)[0]
    second_csrf = mobile_app._SESSIONS[second_token]["csrf_token"]

    assert first_token != second_token
    assert first_csrf != second_csrf


# ---------------------------------------------------------------------------
# Password-change flow: its own possession-token-bound CSRF field
# ---------------------------------------------------------------------------

def _seed_password_change():
    token = mobile_app._create_password_change_token("50001")
    csrf = mobile_app._PASSWORD_CHANGES[token]["csrf_token"]
    return token, csrf


def _pw_cookie(token):
    return {"Cookie": f"{mobile_app.PASSWORD_CHANGE_COOKIE}={token}"}


PASSWORD_BODY = {"new_password": "brand-new-secure-1", "confirm_password": "brand-new-secure-1"}


def test_password_change_missing_csrf_token_is_rejected(client, monkeypatch, tmp_path):
    _patch_users(monkeypatch, tmp_path, "50001", "SUPER_USER")
    token, _csrf = _seed_password_change()
    resp = client.post("/password-change", data=PASSWORD_BODY, headers=_pw_cookie(token))
    assert resp.status_code == 403


def test_password_change_invalid_csrf_token_is_rejected(client, monkeypatch, tmp_path):
    _patch_users(monkeypatch, tmp_path, "50001", "SUPER_USER")
    token, _csrf = _seed_password_change()
    resp = client.post(
        "/password-change", data={**PASSWORD_BODY, "csrf_token": "wrong"}, headers=_pw_cookie(token)
    )
    assert resp.status_code == 403


def test_password_change_token_from_another_flow_is_rejected(client, monkeypatch, tmp_path):
    _patch_users(monkeypatch, tmp_path, "50001", "SUPER_USER")
    token_a, _csrf_a = _seed_password_change()
    _token_b, csrf_b = _seed_password_change()
    resp = client.post(
        "/password-change", data={**PASSWORD_BODY, "csrf_token": csrf_b}, headers=_pw_cookie(token_a)
    )
    assert resp.status_code == 403


def test_password_change_valid_csrf_token_succeeds(client, monkeypatch, tmp_path):
    _patch_users(monkeypatch, tmp_path, "50001", "SUPER_USER")
    token, csrf = _seed_password_change()
    resp = client.post(
        "/password-change", data={**PASSWORD_BODY, "csrf_token": csrf}, headers=_pw_cookie(token)
    )
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/dashboard"


def _patch_users(monkeypatch, tmp_path, user_id, role):
    import dashboard.auth.css_sign_on as css_sign_on

    users_file = tmp_path / "users.json"
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(users_file))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, users_file))
    users = real_load(users_file)
    css_sign_on.create_user(
        users, {"user_id": "00000", "role": "SUPER_USER"}, user_id, "Fresh Operator", role,
        "temp-initial-pw-1",
    )
    real_save(users, users_file)


# ---------------------------------------------------------------------------
# No actual secret (session token, password) ever appears in any response.
# The CSRF token itself legitimately appears embedded in the re-rendered
# form (that's the whole mechanism -- an attacker triggering the request
# cross-site never gets to read this response, so re-embedding the valid
# token for the user's own retry is correct, not a leak).
# ---------------------------------------------------------------------------

def test_csrf_failure_response_does_not_leak_the_session_token_or_a_stack_trace(client):
    token, _csrf = _seed_session(SUPER_USER_CTX)
    resp = client.post("/controls", data={**CONTROLS_BODY, "csrf_token": "wrong"}, headers=_cookie(token))
    body = resp.content.decode("utf-8", errors="replace")
    assert token not in body
    assert "Traceback" not in body
