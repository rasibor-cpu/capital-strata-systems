"""COM-015: every authenticated, cookie-backed, state-changing route requires CSRF.

COM-014 left the three logout entry points on SameSite=Lax alone. This suite
brings them under the same session-bound synchronizer token already used by
``dashboard/mobile/mobile_app.py``'s /controls, /trade, /users:

  dashboard/web/web_app.py            POST /logout                (HTML form field)
  backend/app/auth/operator_login_router.py
                                      POST /auth/operator/logout  (X-CSRF-Token header)
                                      POST /auth/operator/admin/users/{id}/disable|enable
  dashboard/mobile/mobile_app.py      POST /logout                (HTML form field)

A bearer-header request (never sent automatically by a browser) needs no CSRF
token. Login stays exempt: there is no session yet to protect.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI

import backend.app.auth.auth_audit as auth_audit
import backend.app.auth.token_store as token_store_module
from backend.app.auth import operator_login_router
from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from backend.app.auth.token_store import TokenStore
from dashboard.mobile import mobile_app
from dashboard.web.web_app import create_app
from engine.commercial.commercial_audit import CommercialAuditLog
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_operator_authentication import operator_env  # noqa: F401  (fixture)


@pytest.fixture
def audit_db(tmp_path, monkeypatch):
    monkeypatch.delenv("CSS_AUTH_AUDIT_DB", raising=False)
    db_path = str(tmp_path / "auth_audit.sqlite3")
    monkeypatch.setattr(auth_audit, "DEFAULT_AUTH_AUDIT_DB", db_path)
    return db_path


def _logout_events(db_path):
    return [e for e in CommercialAuditLog(db_path).events(object_type="operator_auth") if e.action == "LOGOUT"]


@pytest.fixture
def store(monkeypatch):
    fresh = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", fresh)
    monkeypatch.setattr(operator_login_router, "token_store", fresh)
    return fresh


def _cookie(token):
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


def _expire(store, token):
    info = store._sessions[token]
    store._sessions[token] = type(info)(
        username=info.username, roles=info.roles, issued_at_utc=info.issued_at_utc,
        expires_at_utc=info.issued_at_utc - timedelta(seconds=1), csrf_token=info.csrf_token,
    )


# ---------------------------------------------------------------------------
# Session store: the token itself
# ---------------------------------------------------------------------------


def test_every_session_gets_its_own_unguessable_csrf_token(store):
    a = store.validate(store.create_session("10001", ["FINCON"]))
    b = store.validate(store.create_session("10001", ["FINCON"]))
    assert a.csrf_token and b.csrf_token and a.csrf_token != b.csrf_token
    assert len(a.csrf_token) >= 40  # token_urlsafe(32)
    assert "csrf_token" not in a.to_public_dict()
    assert a.csrf_token not in repr(a)


# ---------------------------------------------------------------------------
# Web dashboard POST /logout (HTML form)
# ---------------------------------------------------------------------------


@pytest.fixture
def web(store, audit_db):
    return TestClient(create_app())


def test_web_logout_with_valid_csrf_revokes_clears_cookie_and_audits_once(web, store, audit_db):
    token = store.create_session("10001", ["FINCON"])
    csrf = store.validate(token).csrf_token
    resp = web.post("/logout", data={"csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert store.validate(token) is None
    set_cookie = resp.headers.get("set-cookie", "")
    assert f'{SESSION_COOKIE_NAME}=""' in set_cookie and "Max-Age=0" in set_cookie
    events = _logout_events(audit_db)
    assert len(events) == 1 and events[0].actor_id == "10001"


@pytest.mark.parametrize("form", [{}, {"csrf_token": ""}, {"csrf_token": "forged-token"}])
def test_web_logout_without_a_valid_csrf_token_is_rejected(web, store, audit_db, form):
    token = store.create_session("10001", ["FINCON"])
    resp = web.post("/logout", data=form, headers=_cookie(token))
    assert resp.status_code == 403
    assert store.validate(token) is not None  # nothing revoked
    assert "set-cookie" not in resp.headers  # cookie untouched
    assert _logout_events(audit_db) == []
    assert token not in resp.content.decode()


def test_web_logout_rejects_a_token_from_another_session(web, store, audit_db):
    victim = store.create_session("10001", ["FINCON"])
    attacker = store.create_session("10003", ["AUDIT"])
    attacker_csrf = store.validate(attacker).csrf_token
    resp = web.post("/logout", data={"csrf_token": attacker_csrf}, headers=_cookie(victim))
    assert resp.status_code == 403
    assert store.validate(victim) is not None and store.validate(attacker) is not None
    assert _logout_events(audit_db) == []


@pytest.mark.parametrize("kill", ["expire", "revoke"])
def test_web_logout_with_a_dead_session_changes_nothing_and_audits_nothing(web, store, audit_db, kill):
    token = store.create_session("10001", ["FINCON"])
    csrf = store.validate(token).csrf_token
    if kill == "expire":
        _expire(store, token)
    else:
        store.revoke(token)
    resp = web.post("/logout", data={"csrf_token": csrf}, headers=_cookie(token))
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    assert _logout_events(audit_db) == []


def test_old_session_cannot_authenticate_or_log_out_again_after_logout(web, store, audit_db):
    token = store.create_session("10001", ["FINCON"])
    csrf = store.validate(token).csrf_token
    assert web.post("/logout", data={"csrf_token": csrf}, headers=_cookie(token)).status_code == 303
    assert web.get("/dashboard", headers=_cookie(token)).status_code == 303
    assert web.get("/api/v1/mission-control", headers=_cookie(token)).status_code == 401
    # Replaying the same logout is a no-op: no second LOGOUT event.
    web.post("/logout", data={"csrf_token": csrf}, headers=_cookie(token))
    assert len(_logout_events(audit_db)) == 1


@pytest.mark.parametrize("path", ["/dashboard", "/billing", "/trial-contract", "/commercialization-operations"])
def test_every_web_page_renders_a_logout_form_bound_to_this_session(web, store, path):
    mine = store.create_session("10001", ["FINCON"])
    other = store.create_session("10003", ["AUDIT"])
    page = web.get(path, headers=_cookie(mine)).content.decode()
    assert 'action="/logout"' in page
    assert f'value="{store.validate(mine).csrf_token}"' in page
    assert store.validate(other).csrf_token not in page
    assert mine not in page  # the session token itself is never rendered
    assert "<!--css-session-controls-->" not in page


def test_web_login_remains_exempt_from_csrf(operator_env, audit_db, monkeypatch):  # noqa: F811
    # operator_env points css_sign_on at a temp user store with 20001/FINCON;
    # web_app imported load_users/save_users by name, so route those there too
    # (never touch the real data/users.json).
    import dashboard.web.web_app as web_app_module
    from dashboard.auth import css_sign_on

    monkeypatch.setattr(web_app_module, "load_users", css_sign_on.load_users)
    monkeypatch.setattr(web_app_module, "save_users", css_sign_on.save_users)
    web = TestClient(create_app())
    resp = web.post("/login", data={"user_id": "20001", "password": "fincon-pass-1"})
    assert resp.status_code == 303 and resp.headers["location"] == "/dashboard"


# ---------------------------------------------------------------------------
# JSON operator API: POST /auth/operator/logout and admin disable/enable
# ---------------------------------------------------------------------------


def _login(client, user_id, password):
    resp = client.post("/auth/operator/login", json={"user_id": user_id, "password": password})
    assert resp.status_code == 200
    return resp.json()


def test_login_response_carries_the_sessions_csrf_token(operator_env):  # noqa: F811
    body = _login(operator_env, "20001", "fincon-pass-1")
    assert body["csrf_token"] == token_store_module.token_store.validate(body["token"]).csrf_token


def test_api_logout_by_cookie_with_csrf_header_succeeds(operator_env, audit_db):  # noqa: F811
    body = _login(operator_env, "20001", "fincon-pass-1")
    resp = operator_env.post(
        "/auth/operator/logout", headers={**_cookie(body["token"]), "X-CSRF-Token": body["csrf_token"]}
    )
    assert resp.status_code == 200 and resp.json() == {"revoked": True}
    assert token_store_module.token_store.validate(body["token"]) is None
    assert len(_logout_events(audit_db)) == 1


@pytest.mark.parametrize("header", [None, "", "forged-token", "OTHER"])
def test_api_logout_by_cookie_without_a_valid_csrf_header_is_rejected(operator_env, audit_db, header):  # noqa: F811
    body = _login(operator_env, "20001", "fincon-pass-1")
    other = _login(operator_env, "20003", "audit-pass-1")
    headers = dict(_cookie(body["token"]))
    if header == "OTHER":
        headers["X-CSRF-Token"] = other["csrf_token"]
    elif header is not None:
        headers["X-CSRF-Token"] = header
    resp = operator_env.post("/auth/operator/logout", headers=headers)
    assert resp.status_code == 403
    assert token_store_module.token_store.validate(body["token"]) is not None
    assert _logout_events(audit_db) == []
    assert body["token"] not in resp.content.decode()


def test_api_logout_by_bearer_header_needs_no_csrf_token(operator_env):  # noqa: F811
    body = _login(operator_env, "20001", "fincon-pass-1")
    resp = operator_env.post("/auth/operator/logout", headers={"Authorization": f"Bearer {body['token']}"})
    assert resp.status_code == 200 and resp.json() == {"revoked": True}


@pytest.mark.parametrize("kill", ["expire", "revoke", "none"])
def test_api_logout_with_no_live_session_is_401(operator_env, audit_db, kill):  # noqa: F811
    body = _login(operator_env, "20001", "fincon-pass-1")
    store = token_store_module.token_store
    if kill == "expire":
        _expire(store, body["token"])
        headers = {**_cookie(body["token"]), "X-CSRF-Token": body["csrf_token"]}
    elif kill == "revoke":
        store.revoke(body["token"])
        headers = {**_cookie(body["token"]), "X-CSRF-Token": body["csrf_token"]}
    else:
        headers = {}
    assert operator_env.post("/auth/operator/logout", headers=headers).status_code == 401
    assert _logout_events(audit_db) == []


def test_admin_disable_by_cookie_requires_csrf_before_anything_changes(operator_env):  # noqa: F811
    su = _login(operator_env, "20005", "superuser-pass-1")
    target = _login(operator_env, "20001", "fincon-pass-1")
    store = token_store_module.token_store

    no_csrf = operator_env.post("/auth/operator/admin/users/20001/disable", headers=_cookie(su["token"]))
    assert no_csrf.status_code == 403
    assert store.validate(target["token"]) is not None  # not disabled, not revoked

    ok = operator_env.post(
        "/auth/operator/admin/users/20001/disable",
        headers={**_cookie(su["token"]), "X-CSRF-Token": su["csrf_token"]},
    )
    assert ok.status_code == 200 and ok.json()["disabled"] is True
    assert store.validate(target["token"]) is None

    enable_no_csrf = operator_env.post("/auth/operator/admin/users/20001/enable", headers=_cookie(su["token"]))
    assert enable_no_csrf.status_code == 403


def test_admin_disable_by_cookie_with_csrf_still_requires_super_user(operator_env):  # noqa: F811
    audit_user = _login(operator_env, "20003", "audit-pass-1")
    resp = operator_env.post(
        "/auth/operator/admin/users/20001/disable",
        headers={**_cookie(audit_user["token"]), "X-CSRF-Token": audit_user["csrf_token"]},
    )
    assert resp.status_code == 403
    assert "super user" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Mobile POST /logout (HTML form, mobile's own session store)
# ---------------------------------------------------------------------------

MOBILE_CTX = {"user_id": "99999", "display_name": "Mobile Op", "role": "VIEWER", "unit_code": "CORE", "home_branch": "HQ"}


@pytest.fixture
def mobile(audit_db, tmp_path, monkeypatch):
    import dashboard.auth.css_sign_on as css_sign_on
    from tests.test_mobile_csrf import seed_mobile_users

    users_file = tmp_path / "mobile_users.json"
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(users_file))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, users_file))
    seed_mobile_users(users_file, MOBILE_CTX, dict(MOBILE_CTX, user_id="99998"))
    mobile_app._SESSIONS.clear()
    yield TestClient(mobile_app.app)
    mobile_app._SESSIONS.clear()


def _mobile_cookie(token):
    return {"Cookie": f"{mobile_app.SESSION_COOKIE}={token}"}


def test_mobile_logout_with_valid_csrf_revokes_and_audits_once(mobile, audit_db):
    token = mobile_app._create_session(MOBILE_CTX)
    csrf = mobile_app._SESSIONS[token]["csrf_token"]
    resp = mobile.post("/logout", data={"csrf_token": csrf}, headers=_mobile_cookie(token))
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    assert token not in mobile_app._SESSIONS
    assert f'{mobile_app.SESSION_COOKIE}=""' in resp.headers.get("set-cookie", "")
    events = _logout_events(audit_db)
    assert len(events) == 1 and events[0].actor_id == "99999"


@pytest.mark.parametrize("form", [{}, {"csrf_token": "forged-token"}, "OTHER"])
def test_mobile_logout_without_a_valid_csrf_token_is_rejected(mobile, audit_db, form):
    token = mobile_app._create_session(MOBILE_CTX)
    if form == "OTHER":
        other = mobile_app._create_session(dict(MOBILE_CTX, user_id="99998"))
        form = {"csrf_token": mobile_app._SESSIONS[other]["csrf_token"]}
    resp = mobile.post("/logout", data=form, headers=_mobile_cookie(token))
    assert resp.status_code == 403
    assert token in mobile_app._SESSIONS
    assert _logout_events(audit_db) == []
    assert token not in resp.content.decode()


def test_mobile_logout_with_an_expired_session_changes_nothing(mobile, audit_db):
    token = mobile_app._create_session(MOBILE_CTX)
    csrf = mobile_app._SESSIONS[token]["csrf_token"]
    mobile_app._SESSIONS[token]["created"] = 0.0
    resp = mobile.post("/logout", data={"csrf_token": csrf}, headers=_mobile_cookie(token))
    assert resp.status_code == 303 and resp.headers["location"] == "/login"
    assert _logout_events(audit_db) == []


def test_mobile_nav_logout_form_carries_this_sessions_token(mobile):
    mine = mobile_app._create_session(MOBILE_CTX)
    other = mobile_app._create_session(dict(MOBILE_CTX, user_id="99998"))
    page = mobile.get("/dashboard", headers=_mobile_cookie(mine)).content.decode()
    assert f'value="{mobile_app._SESSIONS[mine]["csrf_token"]}"' in page
    assert mobile_app._SESSIONS[other]["csrf_token"] not in page
