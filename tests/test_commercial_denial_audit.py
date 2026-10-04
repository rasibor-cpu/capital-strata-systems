"""Register item #10: every commercial authorization denial is audited exactly once.

Enumerated denial paths (all go through ``actor_from_bearer``):
  client-earnings router      5 routes  (commercial_view_obligations)
  trial-contract router       4 routes  (view / commercial_trial_enroll / commercial_trial_cancel)
  commercialization-ops       1 route
  commercialization-release   1 route
  production-charging         1 route
  payment-collection preflight 1 route
  notification preflight      1 route
  launch-dossier export       1 route
These previously raised 403 with no audit record. They now record one
canonical AUTHORIZATION_DENIED event in the authentication audit trail. The
commercial governance API keeps its own pre-existing ``_log_denial`` into the
commercial audit log and must not *also* write an auth-audit event.
"""
from __future__ import annotations

import pytest

import backend.app.auth.token_store as token_store_module
from backend.app.auth.token_store import TokenStore
from dashboard.web.web_app import create_app
from engine.commercial.commercial_audit import CommercialAuditLog
from tests.asgi_test_client import AsgiTestClient as TestClient
from tests.test_operator_authentication import CANCEL_BODY, ENROLL_BODY

Q = "customer_id=c&account_reference=a&agreement_id=AGR-1&agreement_version=v1&jurisdiction_code=CA-ON&assessed_at=2026-01-01T00:00:00Z"
PERIOD = "policy_id=p&period_start=2026-01-01&period_end=2026-01-31"

DENIAL_ROUTES = [
    ("get", "/api/v1/client-earnings-summary?" + PERIOD, None, "commercial_view_obligations"),
    ("get", "/api/v1/customer-profitability-summary?" + PERIOD, None, "commercial_view_obligations"),
    ("get", "/api/v1/advice-profitability-history?terms_id=t", None, "commercial_view_obligations"),
    ("get", "/api/v1/withdrawable-funds-summary?account_reference=a&account_currency=USD&as_of=x", None,
     "commercial_view_obligations"),
    ("get", "/api/v1/client-earnings-history", None, "commercial_view_obligations"),
    ("get", "/api/v1/commercial-trial/agreement?agreement_id=AGR-1&agreement_version=v1", None,
     "commercial_view_obligations"),
    ("post", "/api/v1/commercial-trial/enroll", ENROLL_BODY, "commercial_trial_enroll"),
    ("post", "/api/v1/commercial-trial/cancel", CANCEL_BODY, "commercial_trial_cancel"),
    ("get", "/api/v1/commercial-trial/status?customer_id=c&account_reference=a&agreement_id=AGR-1"
     "&agreement_version=v1&assessed_at=2026-01-01T00:00:00Z", None, "commercial_view_obligations"),
    ("get", "/api/v1/commercialization-operations/status?" + Q + "&provider_id=p&uat_run_id=u&dossier_id=d", None,
     "commercial_view_obligations"),
    ("get", "/api/v1/commercialization-release/readiness?" + Q + "&provider_id=p", None, "commercial_view_obligations"),
    ("get", "/api/v1/production-charging/readiness?" + Q, None, "commercial_view_obligations"),
    ("get", "/api/v1/payment-collection/preflight?" + Q + "&provider_id=p", None, "commercial_view_obligations"),
    ("get", "/api/v1/customer-notifications/preflight?notification_id=n&provider_id=p", None,
     "commercial_view_obligations"),
    ("get", "/api/v1/launch-dossier/export?dossier_id=d", None, "commercial_view_obligations"),
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    auth_db = str(tmp_path / "auth_audit.sqlite3")
    commercial_db = str(tmp_path / "commercial.sqlite3")
    monkeypatch.setenv("CSS_AUTH_AUDIT_DB", auth_db)
    monkeypatch.setenv("CSS_COMMERCIAL_DB", commercial_db)
    return TestClient(create_app()), store, auth_db, commercial_db


def _denials(db):
    return [e for e in CommercialAuditLog(db).events(object_type="operator_auth") if e.action == "AUTHORIZATION_DENIED"]


def _call(client, method, path, body, headers):
    if method == "post":
        return client.post(path, json=body, headers=headers)
    return client.get(path, headers=headers)


@pytest.mark.parametrize("method,path,body,permission", DENIAL_ROUTES)
def test_permission_denial_is_audited_exactly_once_without_secrets(env, method, path, body, permission):
    client, store, auth_db, _ = env
    token = store.create_session("10009", ["TRADER"])
    resp = _call(client, method, path, body, {"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403

    events = _denials(auth_db)
    assert len(events) == 1
    event = events[0]
    assert (event.actor_id, event.actor_role, event.outcome) == ("10009", "TRADER", "DENIED")
    assert event.details == {"permission": permission}
    recorded = repr(event)
    assert token not in recorded
    assert store.validate(token).csrf_token not in recorded
    if body:
        assert body["customer_id"] not in (event.details or {}).values()


@pytest.mark.parametrize("method,path,body,permission", DENIAL_ROUTES)
def test_anonymous_and_forged_requests_are_401_and_not_logged_as_denials(env, method, path, body, permission):
    client, _store, auth_db, _ = env
    assert _call(client, method, path, body, {}).status_code == 401
    assert _call(client, method, path, body, {"Authorization": "Bearer forged"}).status_code == 401
    assert _denials(auth_db) == []


def test_authorized_access_is_not_logged_as_a_denial(env):
    client, store, auth_db, _ = env
    token = store.create_session("10003", ["AUDIT"])
    resp = client.get("/api/v1/client-earnings-history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code not in (401, 403)
    assert _denials(auth_db) == []


def test_governance_api_denial_is_logged_once_in_its_own_log_not_twice(env):
    client, store, auth_db, commercial_db = env
    token = store.create_session("10009", ["TRADER"])
    resp = client.get("/api/v1/commercial/safety-posture", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    commercial_denials = [e for e in CommercialAuditLog(commercial_db).events(object_type="commercial_api")
                          if e.outcome == "DENIED"]
    assert len(commercial_denials) == 1
    assert _denials(auth_db) == []


def test_denial_events_keep_the_hash_chain_valid(env):
    client, store, auth_db, _ = env
    token = store.create_session("10009", ["TRADER"])
    for method, path, body, _perm in DENIAL_ROUTES:
        _call(client, method, path, body, {"Authorization": f"Bearer {token}"})
    log = CommercialAuditLog(auth_db)
    assert len(_denials(auth_db)) == len(DENIAL_ROUTES)
    assert log.verify().ok
    ids = [e.event_id for e in log.events(object_type="operator_auth")]
    assert len(ids) == len(set(ids))
