"""COM-016: route-level authentication inventory for every servable CSS app.

The operator web dashboard (``dashboard.web.web_app``), the mobile app
(``dashboard.mobile.mobile_app``) and the Phase 1 headless engine API
(``backend.app.main``) are enumerated route by route. Every route must appear
in the classification below; a new, unclassified route fails the suite until
someone decides whether it is public, a signed-in page or a protected API
(default deny for new surface).

Every non-public route is then driven anonymously, with forged, malformed and
expired credentials, with identity/role spoofing headers, and under
environment flags that look like bypasses -- and must fail closed every time.
Authorized acceptance for the privileged routes is asserted alongside, so the
rejections are not passing merely because the route is broken.

The two legacy ``/orchestrate`` entrypoints (root ``main.py`` and
``backend/app/api.py``) cannot be imported and are therefore not servable;
``test_legacy_orchestrate_entrypoints_are_not_servable`` pins that so a
partial revival cannot silently expose an unauthenticated posting route.
"""
from __future__ import annotations

import importlib
import time

import pytest
from starlette.routing import Route, WebSocketRoute

import backend.app.auth.token_store as token_store_module
from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from backend.app.auth.token_store import TokenStore
from dashboard.mobile import mobile_app
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_mobile_csrf import SUPER_USER_CTX, VIEWER_CTX, seed_mobile_users
from tests.test_operator_authentication import CANCEL_BODY, ENROLL_BODY

TRIAL_STATUS_QS = (
    "?customer_id=c&account_reference=a&agreement_id=g&agreement_version=v"
    "&jurisdiction_code=CA&assessed_at=2026-01-01"
)

# ---------------------------------------------------------------------------
# Web dashboard classification. Paths use concrete values for path params;
# each protected API entry is (method, request path, json body).
# ---------------------------------------------------------------------------
WEB_PUBLIC = {
    ("GET", "/"),                               # redirect to /dashboard
    ("GET", "/login"),                          # sign-in form
    ("POST", "/login"),                         # credential check itself
    ("POST", "/logout"),                        # no session -> just clears cookie
    ("GET", "/health"),                         # liveness probe
    ("POST", "/auth/operator/login"),           # credential check itself
    ("POST", "/auth/operator/change-password"), # authenticated by current password
}
WEB_PAGES = {
    "/dashboard", "/positions", "/execution", "/risk-governance", "/market-opportunities",
    "/broker", "/margin", "/billing", "/trial-contract", "/commercialization-operations",
    "/approvals",
}
WEB_WEBSOCKETS = {"/ws/v1/dashboard-state"}  # tests/test_dashboard_websocket_auth.py
WEB_PROTECTED_API = [
    ("POST", "/auth/operator/logout", None),
    ("POST", "/auth/operator/admin/users/{user_id}/disable", None),
    ("POST", "/auth/operator/admin/users/{user_id}/enable", None),
    ("GET", "/auth/operator/me", None),
    ("GET", "/api/v1/dashboard-state", None),
    ("GET", "/api/v1/frontend-state", None),
    ("GET", "/api/v1/account-summary", None),
    ("GET", "/api/v1/positions", None),
    ("GET", "/api/v1/risk", None),
    ("GET", "/api/v1/governance", None),
    ("GET", "/api/v1/opportunities", None),
    ("GET", "/api/v1/broker", None),
    ("GET", "/api/v1/broker-reconciliation", None),
    ("GET", "/api/v1/mission-control", None),
    ("GET", "/api/v1/broker-state", None),
    ("GET", "/api/v1/broker-continuity", None),
    ("GET", "/api/v1/questrade/account-summary", None),
    ("GET", "/api/v1/session10-readiness", None),
    ("GET", "/api/v1/runtime-health", None),
    ("GET", "/api/v1/runtime-alerts", None),
    ("GET", "/api/v1/margin-snapshot", None),
    ("GET", "/api/v1/report-export", None),
    ("GET", "/api/v1/client-earnings-history", None),
    ("GET", "/api/v1/client-earnings-summary?policy_id=p&period_start=2026-01-01&period_end=2026-01-31", None),
    ("GET", "/api/v1/customer-profitability-summary?policy_id=p&period_start=2026-01-01&period_end=2026-01-31", None),
    ("GET", "/api/v1/advice-profitability-history?terms_id=t", None),
    ("GET", "/api/v1/withdrawable-funds-summary?account_reference=a&account_currency=USD&as_of=2026-01-01", None),
    ("GET", "/api/v1/commercial-trial/agreement?agreement_id=AGR-1&agreement_version=v1", None),
    ("POST", "/api/v1/commercial-trial/enroll", ENROLL_BODY),
    ("POST", "/api/v1/commercial-trial/cancel", CANCEL_BODY),
    ("GET", "/api/v1/commercial-trial/status?customer_id=c&account_reference=a&agreement_id=g"
            "&agreement_version=v&assessed_at=2026-01-01T00:00:00Z", None),
    ("GET", "/api/v1/production-charging/readiness" + TRIAL_STATUS_QS, None),
    ("GET", "/api/v1/commercialization-release/readiness" + TRIAL_STATUS_QS + "&provider_id=p", None),
    ("GET", "/api/v1/commercialization-operations/status" + TRIAL_STATUS_QS
            + "&provider_id=p&uat_run_id=u&dossier_id=d", None),
    ("GET", "/api/v1/payment-collection/preflight" + TRIAL_STATUS_QS + "&provider_id=p", None),
    ("GET", "/api/v1/customer-notifications/preflight?notification_id=n&provider_id=p", None),
    ("GET", "/api/v1/launch-dossier/export?dossier_id=d", None),
    ("GET", "/api/v1/commercial/safety-posture", None),
    ("GET", "/api/v1/commercial/reconciliation/exceptions", None),
    ("POST", "/api/v1/commercial/reconciliation/exceptions/{exception_id}/resolution-requests",
     {"resolution_reference": "r", "idempotency_key": "k"}),
    ("GET", "/api/v1/commercial/controlled-actions", None),
    ("POST", "/api/v1/commercial/controlled-actions/{action_id}/approve", {"expected_payload_hash": "0" * 64}),
    ("POST", "/api/v1/commercial/controlled-actions/{action_id}/reject",
     {"expected_payload_hash": "0" * 64, "reason": "r"}),
    ("GET", "/api/v1/commercial/customers/{customer_id}/statement", None),
    ("GET", "/api/v1/commercial/audit", None),
]

# ---------------------------------------------------------------------------
# Mobile app classification.
# ---------------------------------------------------------------------------
MOBILE_PUBLIC = {
    ("GET", "/"), ("GET", "/login"), ("POST", "/login"),
    ("GET", "/password-change"),   # redirects without the possession cookie
    ("POST", "/password-change"),  # authenticated by the possession cookie
    ("POST", "/logout"),
    ("GET", "/manifest.webmanifest"), ("GET", "/service-worker.js"), ("GET", "/icon.svg"),
    # Same system-posture fields the sign-in page's status strip already shows
    # pre-authentication; no account, position or financial data.
    ("GET", "/api/status"),
}
MOBILE_PAGES = [
    ("GET", "/dashboard"), ("GET", "/positions"), ("GET", "/history"), ("GET", "/risk"),
    ("GET", "/governance"), ("GET", "/opportunities"), ("GET", "/market"), ("GET", "/broker"),
    ("GET", "/margin"), ("GET", "/audit"), ("GET", "/trade-status"), ("GET", "/controls"),
    ("POST", "/controls"), ("GET", "/trade"), ("POST", "/trade"), ("GET", "/users"), ("POST", "/users"),
]
MOBILE_PROTECTED_API = ["/api/margin-snapshot", "/api/audit/export", "/api/audit/replay"]

# ---------------------------------------------------------------------------
# Hostile inputs.
# ---------------------------------------------------------------------------
SPOOF_HEADERS = [
    {"X-Forwarded-User": "00000"},
    {"X-User-Id": "00000", "X-Role": "SUPER_USER"},
    {"X-CSS-Role": "SUPER_USER", "X-CSS-User": "00000"},
    {"X-Remote-User": "admin"},
    {"X-Debug": "1", "X-Internal-Request": "1", "X-Auth-Bypass": "1"},
    {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"},
]
MALFORMED_AUTHORIZATION = [
    "Bearer", "Bearer ", "Bearer null", "Bearer undefined", "Bearer a b",
    "Basic MDAwMDA6cGFzc3dvcmQ=", "Token abc", "bearer\tforged", "forged",
]
BYPASS_LOOKING_ENV = {
    "CSS_ENV": "development", "DEBUG": "1", "CSS_DEBUG": "1", "CSS_AUTH_DISABLED": "1",
    "AUTH_DISABLED": "true", "CSS_AUTH_BYPASS": "1", "SKIP_AUTH": "1", "DISABLE_AUTH": "1",
    "HEADLESS_DEV_MODE": "true", "REA_ALLOW_DEFAULT_CREDS": "1", "CSS_AUTH_UI": "cli",
    "TESTING": "1", "PYTEST_CURRENT_TEST": "x",
}


def _concrete(path):
    return (path.replace("{user_id}", "10003").replace("{exception_id}", "x")
            .replace("{action_id}", "x").replace("{customer_id}", "cust-1"))


def _cookie(token):
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


@pytest.fixture
def store(monkeypatch):
    fresh = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", fresh)
    return fresh


def _build_web():
    from dashboard.web.web_app import create_app

    return create_app()


@pytest.fixture
def web_env(tmp_path, monkeypatch):
    # Mount the commercial governance API too, so its routes are inventoried.
    monkeypatch.setenv("CSS_COMMERCIAL_DB", str(tmp_path / "commercial.sqlite3"))
    monkeypatch.delenv("CSS_ENV", raising=False)


@pytest.fixture
def web(store, web_env):
    return TestClient(_build_web())


@pytest.fixture
def mobile(monkeypatch, tmp_path):
    mobile_app._SESSIONS.clear()
    mobile_app._PASSWORD_CHANGES.clear()
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    import dashboard.auth.css_sign_on as css_sign_on

    users_file = tmp_path / "users.json"
    real_load, real_save = css_sign_on.load_users, css_sign_on.save_users
    monkeypatch.setattr(mobile_app, "load_users", lambda *_a, **_k: real_load(users_file))
    monkeypatch.setattr(mobile_app, "save_users", lambda users, *_a, **_k: real_save(users, users_file))
    seed_mobile_users(users_file, SUPER_USER_CTX, VIEWER_CTX)
    yield TestClient(mobile_app.app)
    mobile_app._SESSIONS.clear()
    mobile_app._PASSWORD_CHANGES.clear()


@pytest.fixture
def engine_api(store, monkeypatch):
    monkeypatch.delenv("CSS_ENV", raising=False)
    import backend.app.main as engine_main

    return TestClient(importlib.reload(engine_main).app)


def _http_routes(app):
    out = set()
    for route in app.routes:
        if isinstance(route, Route) and not isinstance(route, WebSocketRoute):
            out |= {(m, route.path) for m in route.methods - {"HEAD"}}
    return out


# ---------------------------------------------------------------------------
# 1. Inventory: every route is classified (default deny for new surface).
# ---------------------------------------------------------------------------
def test_every_web_route_is_classified(store, web_env):
    app = _build_web()
    classified = (
        WEB_PUBLIC
        | {("GET", p) for p in WEB_PAGES}
        | {(m, p.split("?")[0]) for m, p, _ in WEB_PROTECTED_API}
    )
    actual = _http_routes(app)
    assert actual - classified == set(), "unclassified web routes -- classify them in this file"
    assert classified - actual == set(), "classified web routes no longer exist"
    ws = {r.path for r in app.routes if isinstance(r, WebSocketRoute)}
    assert ws == WEB_WEBSOCKETS


def test_every_mobile_route_is_classified():
    classified = MOBILE_PUBLIC | set(MOBILE_PAGES) | {("GET", p) for p in MOBILE_PROTECTED_API}
    actual = _http_routes(mobile_app.app)
    assert actual - classified == set(), "unclassified mobile routes -- classify them in this file"
    assert classified - actual == set()


def test_every_engine_api_route_is_classified(engine_api):
    assert _http_routes(engine_api.app) == {("GET", "/health"), ("POST", "/engine/headless/run")}


# ---------------------------------------------------------------------------
# 2. Web: protected APIs fail closed for every hostile credential.
# ---------------------------------------------------------------------------
def _call(client, method, path, body, headers=None):
    return client.request(method, _concrete(path), headers=headers or {}, json=body)


@pytest.mark.parametrize("method,path,body", WEB_PROTECTED_API)
def test_web_protected_api_rejects_anonymous_forged_and_expired(web, store, method, path, body):
    expired = store.create_session("10003", ["SUPER_USER"], minutes=-1)
    revoked = store.create_session("10003", ["SUPER_USER"])
    store.revoke(revoked)
    attempts = [
        {},
        {"Authorization": "Bearer forged-token"},
        _cookie("forged-token"),
        {"Authorization": f"Bearer {expired}"},
        _cookie(expired),
        {"Authorization": f"Bearer {revoked}"},
        *({"Authorization": value} for value in MALFORMED_AUTHORIZATION),
        *SPOOF_HEADERS,
    ]
    for headers in attempts:
        resp = _call(web, method, path, body, headers)
        assert resp.status_code == 401, (headers, resp.status_code, resp.content[:200])


@pytest.mark.parametrize("method,path,body", WEB_PROTECTED_API)
def test_web_protected_api_ignores_bypass_looking_environment(store, web_env, monkeypatch, method, path, body):
    for name, value in BYPASS_LOOKING_ENV.items():
        monkeypatch.setenv(name, value)
    client = TestClient(_build_web())
    assert _call(client, method, path, body).status_code == 401
    assert _call(client, method, path, body, SPOOF_HEADERS[1]).status_code == 401


@pytest.mark.parametrize("path", sorted(WEB_PAGES))
def test_web_pages_redirect_every_unauthenticated_caller_to_login(web, store, path):
    expired = store.create_session("10003", ["SUPER_USER"], minutes=-1)
    for headers in ({}, _cookie("forged-token"), _cookie(expired), {"Authorization": "Bearer forged"}, *SPOOF_HEADERS):
        resp = web.get(path, headers=headers)
        assert resp.status_code == 303, (headers, resp.status_code)
        assert resp.headers["location"] == "/login"


@pytest.mark.parametrize("path", sorted(WEB_PAGES))
def test_web_pages_render_for_a_signed_in_operator(web, store, path):
    token = store.create_session("10009", ["TRADER"])
    assert web.get(path, headers=_cookie(token)).status_code == 200


def test_web_health_is_public_but_carries_no_account_data(web):
    body = web.get("/health").json()
    assert set(body) == {"ok", "session_id", "resolved_mode", "engine_mode"}


# ---------------------------------------------------------------------------
# 3. Authorized vs unauthorized on the privileged routes.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,body", [
    ("/api/v1/commercial-trial/enroll", ENROLL_BODY),
    ("/api/v1/commercial-trial/cancel", CANCEL_BODY),
])
def test_trial_mutations_need_the_trial_grant_and_only_create_a_pending_request(web, store, path, body):
    for role in ("TRADER", "AUDIT", "SUPER_USER", "ADMIN", "TECH"):
        token = store.create_session("10009", [role])
        resp = web.post(path, json=body, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403, (role, resp.content)
    maker = store.create_session("10001", ["FINCON"])
    ok = web.post(path, json=body, headers={"Authorization": f"Bearer {maker}"})
    assert ok.status_code == 201, ok.content
    data = ok.json()
    assert data["controlled_action"]["status"] == "PENDING"
    assert data["execution_authority"] is False
    assert data["money_movement_allowed"] is False


def test_controlled_action_approval_needs_the_checker_grant(web, store):
    for role in ("FINCON", "AUDIT", "TRADER", "SUPER_USER"):
        token = store.create_session("10009", [role])
        resp = web.post("/api/v1/commercial/controlled-actions/x/approve",
                        json={"expected_payload_hash": "0" * 64},
                        headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403, (role, resp.content)


def test_operator_admin_disable_needs_super_user(web, store):
    for role in ("ADMIN", "AUDIT", "HEAD_FINCON", "TRADER"):
        token = store.create_session("10009", [role])
        resp = web.post("/auth/operator/admin/users/10003/disable", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403, (role, resp.content)


# ---------------------------------------------------------------------------
# 4. Headless engine run (was anonymously reachable before COM-016).
# ---------------------------------------------------------------------------
RUN = "/engine/headless/run"


def test_engine_run_rejects_anonymous_forged_expired_and_spoofed(engine_api, store):
    expired = store.create_session("00000", ["SUPER_USER"], minutes=-1)
    for headers in ({}, {"Authorization": "Bearer forged"}, {"Authorization": f"Bearer {expired}"},
                    # The route is bearer-only: a valid session cookie is not accepted.
                    _cookie(store.create_session("00000", ["SUPER_USER"])),
                    *({"Authorization": v} for v in MALFORMED_AUTHORIZATION), *SPOOF_HEADERS):
        resp = engine_api.post(RUN, json={"steps": 1}, headers=headers)
        assert resp.status_code == 401, (headers, resp.status_code, resp.content[:200])


@pytest.mark.parametrize("role", ["ADMIN", "TECH", "HEAD_TECH", "TRADER", "RISK", "AUDIT", "FINCON", "VIEWER", "UNKNOWN"])
def test_engine_run_rejects_roles_without_manage_system(engine_api, store, role):
    token = store.create_session("10009", [role])
    resp = engine_api.post(RUN, json={"steps": 1}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_engine_run_denial_is_audited(engine_api, store, tmp_path, monkeypatch):
    from engine.commercial.commercial_audit import CommercialAuditLog

    db = str(tmp_path / "audit.sqlite3")
    monkeypatch.setenv("CSS_AUTH_AUDIT_DB", db)
    token = store.create_session("10009", ["TRADER"])
    engine_api.post(RUN, json={"steps": 1}, headers={"Authorization": f"Bearer {token}"})
    denied = [e for e in CommercialAuditLog(db).events(object_type="operator_auth")
              if e.action == "AUTHORIZATION_DENIED"]
    assert len(denied) == 1
    assert denied[0].actor_id == "10009"


def test_engine_run_accepts_super_user_and_stays_fail_closed(engine_api, store):
    token = store.create_session("00000", ["SUPER_USER"])
    headers = {"Authorization": f"Bearer {token}"}
    ok = engine_api.post(RUN, json={"steps": 1}, headers=headers)
    assert ok.status_code == 200
    # Authentication grants a run, never live execution.
    live = engine_api.post(RUN, json={"steps": 1, "execution_mode": "LIVE"}, headers=headers).json()
    assert live.get("ok") is False


def test_engine_run_ignores_bypass_looking_environment(store, monkeypatch):
    for name, value in BYPASS_LOOKING_ENV.items():
        monkeypatch.setenv(name, value)
    import backend.app.main as engine_main

    client = TestClient(importlib.reload(engine_main).app)
    assert client.post(RUN, json={"steps": 1}).status_code == 401
    assert client.post(RUN, json={"steps": 1}, headers=SPOOF_HEADERS[1]).status_code == 401


# ---------------------------------------------------------------------------
# 5. Mobile.
# ---------------------------------------------------------------------------
def _mobile_expired_session():
    token = mobile_app._create_session(SUPER_USER_CTX)
    mobile_app._SESSIONS[token]["created"] = time.time() - mobile_app.SESSION_MAX_SECONDS - 5
    return token


def _mobile_cookie(token):
    return {"Cookie": f"{mobile_app.SESSION_COOKIE}={token}"}


@pytest.mark.parametrize("method,path", MOBILE_PAGES)
def test_mobile_pages_redirect_every_unauthenticated_caller(mobile, method, path):
    for headers in ({}, _mobile_cookie("forged"), _mobile_cookie(_mobile_expired_session()),
                    _cookie("forged"), *SPOOF_HEADERS):
        resp = mobile.request(method, path, headers=headers, data={} if method == "POST" else None)
        assert resp.status_code == 303, (headers, resp.status_code)
        assert resp.headers["location"] == "/login"


@pytest.mark.parametrize("path", MOBILE_PROTECTED_API)
def test_mobile_apis_return_401_to_every_unauthenticated_caller(mobile, path):
    for headers in ({}, _mobile_cookie("forged"), _mobile_cookie(_mobile_expired_session()),
                    {"Authorization": "Bearer forged"}, *SPOOF_HEADERS):
        resp = mobile.get(path, headers=headers)
        assert resp.status_code == 401, (path, headers, resp.status_code)
        assert resp.json()["ok"] is False


def test_mobile_audit_api_needs_the_audit_grant(mobile):
    viewer = mobile_app._create_session(VIEWER_CTX)
    assert mobile.get("/api/audit/export", headers=_mobile_cookie(viewer)).status_code == 403
    admin = mobile_app._create_session(SUPER_USER_CTX)
    assert mobile.get("/api/audit/export", headers=_mobile_cookie(admin)).status_code == 200


def test_mobile_status_exposes_only_the_sign_in_page_posture(mobile):
    body = mobile.get("/api/status").json()
    assert body["authenticated"] is False
    assert body["live_orders_enabled"] is False
    assert set(body) == {
        "ok", "authenticated", "mode", "system_mode", "orders_enabled", "engine_mode",
        "broker_live_gate", "live_order_kill_switch", "live_orders_enabled",
    }


# ---------------------------------------------------------------------------
# 6. Interactive API docs are off unless development is declared.
# ---------------------------------------------------------------------------
DOC_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")


def test_api_docs_are_not_served_by_default(web, mobile, engine_api):
    assert mobile_app.app.openapi_url is None, "mobile app was imported with CSS_ENV=development"
    for client in (web, mobile, engine_api):
        for path in DOC_PATHS:
            assert client.get(path).status_code == 404, (client.app.title, path)


def test_api_docs_only_with_declared_development(store, web_env, monkeypatch):
    monkeypatch.setenv("CSS_ENV", "development")
    client = TestClient(_build_web())
    assert client.get("/openapi.json").status_code == 200
    # Declaring development exposes the schema, never the data behind it.
    assert client.get("/api/v1/mission-control").status_code == 401


def test_in_process_schema_generation_still_works(store, web_env):
    assert "/api/v1/mission-control" in _build_web().openapi()["paths"]


# ---------------------------------------------------------------------------
# 7. Restart: protection is rebuilt, pre-restart sessions do not survive.
# ---------------------------------------------------------------------------
def test_route_auth_survives_a_restart_and_old_sessions_die(store, web_env, monkeypatch):
    before = TestClient(_build_web())
    token = store.create_session("10003", ["AUDIT"])
    assert before.get("/api/v1/mission-control", headers=_cookie(token)).status_code == 200

    # Restart: fresh process state (new in-memory session store, new app).
    monkeypatch.setattr(token_store_module, "token_store", TokenStore())
    after = TestClient(_build_web())
    for method, path, body in WEB_PROTECTED_API:
        assert _call(after, method, path, body).status_code == 401, path
    assert after.get("/api/v1/mission-control", headers=_cookie(token)).status_code == 401
    assert after.get("/api/v1/mission-control", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert after.get("/openapi.json").status_code == 404


def test_engine_run_auth_survives_a_module_reload(store, monkeypatch):
    import backend.app.main as engine_main

    for _ in range(2):
        client = TestClient(importlib.reload(engine_main).app)
        assert client.post(RUN, json={"steps": 1}).status_code == 401


def test_mobile_sessions_do_not_survive_a_restart(mobile):
    token = mobile_app._create_session(SUPER_USER_CTX)
    assert mobile.get("/api/audit/export", headers=_mobile_cookie(token)).status_code == 200
    mobile_app._SESSIONS.clear()  # process restart: the in-memory store is empty
    assert mobile.get("/api/audit/export", headers=_mobile_cookie(token)).status_code == 401


# ---------------------------------------------------------------------------
# 8. Legacy entrypoints.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("module", ["main", "backend.app.api"])
def test_legacy_orchestrate_entrypoints_are_not_servable(module):
    with pytest.raises(ImportError):
        importlib.import_module(module)
