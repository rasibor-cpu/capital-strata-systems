"""Register item #5: commercial routes the operator web pages call must accept the session cookie.

``/billing``, ``/trial-contract`` and ``/commercialization-operations`` are
cookie-authenticated pages whose embedded JavaScript calls client-earnings,
commercial-trial and launch-ops status routes same-origin. Those routes were
bearer-header-only, so every in-page call returned 401 for a signed-in
operator. They now also accept the session cookie; identity, role and
permission are still resolved entirely server-side by ``actor_from_bearer``,
and a cookie-backed POST (trial enroll/cancel) additionally needs the
session's CSRF token.

Commercial routes with no browser caller (governance API, production
charging, release readiness, payment/notification preflight, launch-dossier
export) deliberately stay bearer-only.
"""
from __future__ import annotations

import pytest

import backend.app.auth.token_store as token_store_module
from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from backend.app.auth.token_store import TokenStore
from dashboard.web.web_app import create_app
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_operator_authentication import CANCEL_BODY, ENROLL_BODY


@pytest.fixture
def store(monkeypatch):
    fresh = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", fresh)
    return fresh


@pytest.fixture
def web(store, tmp_path, monkeypatch):
    monkeypatch.setenv("CSS_COMMERCIAL_DB", str(tmp_path / "commercial.sqlite3"))
    monkeypatch.setenv("CSS_AUTH_AUDIT_DB", str(tmp_path / "auth_audit.sqlite3"))
    return TestClient(create_app())


def _cookie(token):
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


BROWSER_READ_PATHS = [
    "/api/v1/client-earnings-history",
    "/api/v1/client-earnings-summary?policy_id=p&period_start=2026-01-01&period_end=2026-01-31",
    "/api/v1/customer-profitability-summary?policy_id=p&period_start=2026-01-01&period_end=2026-01-31",
    "/api/v1/advice-profitability-history?terms_id=unknown",
    "/api/v1/commercial-trial/agreement?agreement_id=AGR-1&agreement_version=v1",
    "/api/v1/commercial-trial/status?customer_id=c&account_reference=a&agreement_id=AGR-1"
    "&agreement_version=v1&assessed_at=2026-01-01T00:00:00Z",
    "/api/v1/commercialization-operations/status?customer_id=c&account_reference=a&agreement_id=AGR-1"
    "&agreement_version=v1&jurisdiction_code=CA-ON&assessed_at=2026-01-01T00:00:00Z&provider_id=p"
    "&uat_run_id=u&dossier_id=d",
]


@pytest.mark.parametrize("path", BROWSER_READ_PATHS)
def test_browser_read_routes_accept_an_authorized_session_cookie(web, store, path):
    token = store.create_session("10003", ["AUDIT"])
    resp = web.get(path, headers=_cookie(token))
    # Authentication and authorization passed; any 404/409/422 is the route's
    # own business answer for this synthetic input, never an auth failure.
    assert resp.status_code not in (401, 403), resp.content


@pytest.mark.parametrize("path", BROWSER_READ_PATHS)
def test_browser_read_routes_still_reject_anonymous_forged_and_wrong_role_cookies(web, store, path):
    assert web.get(path).status_code == 401
    assert web.get(path, headers=_cookie("forged-token")).status_code == 401
    trader = store.create_session("10009", ["TRADER"])
    assert web.get(path, headers=_cookie(trader)).status_code == 403


@pytest.mark.parametrize("path", BROWSER_READ_PATHS)
def test_bearer_clients_are_unaffected(web, store, path):
    token = store.create_session("10003", ["AUDIT"])
    assert web.get(path, headers={"Authorization": f"Bearer {token}"}).status_code not in (401, 403)


@pytest.mark.parametrize("path,body", [
    ("/api/v1/commercial-trial/enroll", ENROLL_BODY),
    ("/api/v1/commercial-trial/cancel", CANCEL_BODY),
])
def test_cookie_backed_trial_mutation_requires_csrf_and_goes_to_maker_checker(web, store, path, body):
    maker = store.create_session("10001", ["FINCON"])
    csrf = store.validate(maker).csrf_token
    other_csrf = store.validate(store.create_session("10002", ["HEAD_FINCON"])).csrf_token

    for headers in (
        _cookie(maker),
        {**_cookie(maker), "X-CSRF-Token": "forged-token"},
        {**_cookie(maker), "X-CSRF-Token": other_csrf},
    ):
        resp = web.post(path, json=body, headers=headers)
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    ok = web.post(path, json=body, headers={**_cookie(maker), "X-CSRF-Token": csrf})
    assert ok.status_code == 201, ok.content
    data = ok.json()
    # Still only a *request*: a second authorized approver must approve it.
    assert data["controlled_action"]["status"] == "PENDING"
    assert data["controlled_action"]["maker_id"] == "10001"
    assert data["payment_execution_allowed"] is False
    assert data["money_movement_allowed"] is False
    assert data["execution_authority"] is False


def test_cookie_backed_trial_mutation_with_csrf_still_enforces_role(web, store):
    audit = store.create_session("10003", ["AUDIT"])  # view rights only
    resp = web.post(
        "/api/v1/commercial-trial/enroll", json=ENROLL_BODY,
        headers={**_cookie(audit), "X-CSRF-Token": store.validate(audit).csrf_token},
    )
    assert resp.status_code == 403
    assert "CSRF" not in resp.json()["detail"]


@pytest.mark.parametrize("kill", ["expire", "revoke"])
def test_cookie_backed_trial_mutation_with_a_dead_session_is_401(web, store, kill):
    from datetime import timedelta

    maker = store.create_session("10001", ["FINCON"])
    info = store.validate(maker)
    if kill == "expire":
        store._sessions[maker] = type(info)(
            username=info.username, roles=info.roles, issued_at_utc=info.issued_at_utc,
            expires_at_utc=info.issued_at_utc - timedelta(seconds=1), csrf_token=info.csrf_token,
        )
    else:
        store.revoke(maker)
    resp = web.post(
        "/api/v1/commercial-trial/enroll", json=ENROLL_BODY,
        headers={**_cookie(maker), "X-CSRF-Token": info.csrf_token},
    )
    assert resp.status_code == 401


def test_bearer_trial_mutation_needs_no_csrf(web, store):
    maker = store.create_session("10001", ["FINCON"])
    resp = web.post("/api/v1/commercial-trial/enroll", json=ENROLL_BODY, headers={"Authorization": f"Bearer {maker}"})
    assert resp.status_code == 201


API_ONLY_PATHS = [
    "/api/v1/production-charging/readiness",
    "/api/v1/commercialization-release/readiness",
    "/api/v1/payment-collection/preflight",
    "/api/v1/customer-notifications/preflight",
    "/api/v1/launch-dossier/export",
    "/api/v1/commercial/safety-posture",
    "/api/v1/commercial/controlled-actions",
]


@pytest.mark.parametrize("path", API_ONLY_PATHS)
def test_api_only_commercial_routes_stay_bearer_only(web, store, path):
    token = store.create_session("10003", ["AUDIT"])
    assert web.get(path, headers=_cookie(token)).status_code in (401, 422)
    # 422 would mean query validation ran first; either way the cookie never
    # authenticated anything. Confirm the bearer path for the same session works
    # for a route with no required query params.
    if path.startswith("/api/v1/commercial/"):
        assert web.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_trial_page_script_sends_the_csrf_header_and_an_idempotency_key(web, store):
    token = store.create_session("10001", ["FINCON"])
    page = web.get("/trial-contract", headers=_cookie(token)).content.decode()
    assert '"X-CSRF-Token"' in page
    assert page.count("idempotency_key: trialIdempotencyKey(") == 2
    assert 'id="css-csrf-token"' in page
