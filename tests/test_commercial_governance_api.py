"""Authenticated commercial governance API: authentication, RBAC and
maker-checker enforced server-side, with no money-movement surface."""
import sqlite3
from decimal import Decimal

import pytest
from fastapi import FastAPI
from tests.asgi_test_client import AsgiTestClient as TestClient

from dashboard.runtime.commercial_governance_router import (
    SAFETY_POSTURE,
    create_commercial_governance_router,
    token_store_session_resolver,
)
from engine.commercial.collection_history import CollectionHistoryRepository
from engine.commercial.collection_repository import CollectionRepository
from engine.commercial.collection_service import CollectionService
from engine.commercial.commercial_audit import CommercialAuditLog
from engine.commercial.commercial_controls import (
    CommercialControls,
    ControlledActionStore,
    reconciliation_resolution_action,
)
from engine.commercial.reconciliation_repository import ReconciliationRepository
from engine.commercial.reconciliation_service import ReconciliationService, SettlementEvidence
from engine.domain.collections import CollectionStatus, CollectionTransaction
from engine.ledger.ledger_store import LedgerStore

SESSIONS = {
    "tok-maker": ("fincon-01", ("FINCON",)),
    "tok-checker": ("head-fincon-01", ("HEAD_FINCON",)),
    "tok-compliance-head": ("head-compliance-01", ("HEAD_COMPLIANCE",)),
    "tok-auditor": ("audit-01", ("AUDIT",)),
    "tok-trader": ("trader-01", ("TRADER",)),
    "tok-super": ("root", ("SUPER_USER",)),
    "tok-multi": ("multi-01", ("VIEWER", "HEAD_FINCON")),
    "tok-norole": ("nobody", ()),
}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def env(tmp_path):
    db = str(tmp_path / "commercial.sqlite3")
    recon = ReconciliationService(ReconciliationRepository(db))
    audit = CommercialAuditLog(db)
    controls = CommercialControls(ControlledActionStore(db), audit)
    controls.register(reconciliation_resolution_action(recon))
    collections = CollectionRepository(db)
    history = CollectionHistoryRepository(db)

    service = CollectionService(LedgerStore(), history=history)
    c = CollectionTransaction(obligation_id="obl-1", customer_id="cust-1", account_id="acct-1",
                              amount=Decimal("25.00"), currency="CAD", idempotency_key="k-1")
    service.register(c)
    service.transition(c, CollectionStatus.INITIATED, provider_reference="p-1")
    service.transition(c, CollectionStatus.AUTHORIZED, provider_reference="p-1")
    service.transition(c, CollectionStatus.SETTLED, settlement_reference="s-1")
    service.post_settlement(c, "settle-acct")
    collections.save(c)
    recon.reconcile(c, SettlementEvidence(c.collection_id, "p-1", "s-1", Decimal("24.99"), "CAD"))

    app = FastAPI()
    app.router.routes.extend(create_commercial_governance_router(
        controls=controls, reconciliation=recon, collections=collections, history=history, audit=audit,
        session_resolver=SESSIONS.get,
    ).routes)
    return TestClient(app), recon, controls, audit, db


def _exception_id(client):
    return client.get("/api/v1/commercial/reconciliation/exceptions", headers=bearer("tok-auditor")).json()["open_exceptions"][0]["exception_id"]


def _request(client, exception_id, token="tok-maker", key="req-1"):
    return client.post(f"/api/v1/commercial/reconciliation/exceptions/{exception_id}/resolution-requests",
                       json={"resolution_reference": "ticket-7", "idempotency_key": key}, headers=bearer(token))


ROUTES = [
    ("get", "/api/v1/commercial/safety-posture", None),
    ("get", "/api/v1/commercial/reconciliation/exceptions", None),
    ("get", "/api/v1/commercial/controlled-actions", None),
    ("get", "/api/v1/commercial/customers/cust-1/statement", None),
    ("get", "/api/v1/commercial/audit", None),
    ("post", "/api/v1/commercial/reconciliation/exceptions/x/resolution-requests", {"resolution_reference": "r", "idempotency_key": "k"}),
    ("post", "/api/v1/commercial/controlled-actions/x/approve", {"expected_payload_hash": "0" * 64}),
    ("post", "/api/v1/commercial/controlled-actions/x/reject", {"expected_payload_hash": "0" * 64, "reason": "r"}),
]


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "tok-maker"}, {"Authorization": "Basic tok-maker"}, bearer(""), bearer("forged-token")])
def test_every_route_requires_a_valid_bearer_session(env, method, path, body, headers):
    client = env[0]
    response = getattr(client, method)(path, headers=headers, **({"json": body} if body else {}))
    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", ROUTES)
@pytest.mark.parametrize("token", ["tok-trader", "tok-super", "tok-norole"])
def test_non_commercial_sessions_are_forbidden_everywhere(env, method, path, body, token):
    client = env[0]
    response = getattr(client, method)(path, headers=bearer(token), **({"json": body} if body else {}))
    assert response.status_code == 403


def test_identity_cannot_be_supplied_in_the_request(env):
    client, _, controls, _, _ = env
    exception_id = _exception_id(client)
    response = client.post(f"/api/v1/commercial/reconciliation/exceptions/{exception_id}/resolution-requests",
                           json={"resolution_reference": "t", "idempotency_key": "k", "maker_id": "head-fincon-01", "role": "HEAD_FINCON"},
                           headers=bearer("tok-maker"))
    assert response.status_code == 201
    assert response.json()["controlled_action"]["maker_id"] == "fincon-01"


def test_maker_checker_flow_over_http(env):
    client, recon, _, audit, _ = env
    exception_id = _exception_id(client)
    assert _request(client, exception_id, token="tok-auditor").status_code == 403
    created = _request(client, exception_id)
    assert created.status_code == 201
    action = created.json()["controlled_action"]
    assert created.json()["safety"] == SAFETY_POSTURE

    assert client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                       json={"expected_payload_hash": action["payload_hash"]}, headers=bearer("tok-maker")).status_code == 403
    bad = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                      json={"expected_payload_hash": "f" * 64}, headers=bearer("tok-checker"))
    assert bad.status_code == 422
    malformed = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                            json={"expected_payload_hash": "Z" * 64}, headers=bearer("tok-checker"))
    assert malformed.status_code == 422
    assert isinstance(malformed.json()["detail"], list), "malformed hashes must be rejected by request validation"

    ok = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                     json={"expected_payload_hash": action["payload_hash"], "evidence_ref": "stmt-1"}, headers=bearer("tok-checker"))
    assert ok.status_code == 200 and ok.json()["controlled_action"]["status"] == "EXECUTED"
    assert ok.json()["controlled_action"]["checker_id"] == "head-fincon-01"
    assert recon.open_exceptions() == []

    replay = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                         json={"expected_payload_hash": action["payload_hash"]}, headers=bearer("tok-compliance-head"))
    assert replay.status_code == 409
    assert audit.verify().ok


def test_self_approval_through_api_is_refused_for_a_maker_who_is_also_a_checker(env):
    client = env[0]
    exception_id = _exception_id(client)
    action = _request(client, exception_id, token="tok-checker").json()["controlled_action"]
    response = client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                           json={"expected_payload_hash": action["payload_hash"]}, headers=bearer("tok-checker"))
    assert response.status_code == 422 and "maker cannot check" in response.json()["detail"]


def test_multi_role_session_acts_under_the_granting_role(env):
    client = env[0]
    exception_id = _exception_id(client)
    action = _request(client, exception_id, token="tok-multi").json()["controlled_action"]
    assert action["maker_role"] == "HEAD_FINCON"


def test_statement_and_audit_views_are_permission_scoped(env):
    client = env[0]
    statement = client.get("/api/v1/commercial/customers/cust-1/statement", headers=bearer("tok-maker"))
    assert statement.status_code == 200
    body = statement.json()["statement"]
    assert body["lines"][0]["state"] == "settled" and body["lines"][0]["has_open_exception"] is True
    assert body["totals"]["CAD"]["paid"] == "0.00"
    assert client.get("/api/v1/commercial/audit", headers=bearer("tok-maker")).status_code == 403
    audit = client.get("/api/v1/commercial/audit", headers=bearer("tok-auditor"))
    assert audit.status_code == 200 and audit.json()["chain_verified"] is True


def test_audit_view_reports_tampering(env):
    client, _, _, _, db = env
    _request(client, _exception_id(client))
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER commercial_audit_events_no_update")
    conn.execute("UPDATE commercial_audit_events SET actor_id='mallory'")
    conn.commit()
    conn.close()
    body = client.get("/api/v1/commercial/audit", headers=bearer("tok-auditor")).json()
    assert body["chain_verified"] is False and body["first_invalid_seq"] is not None


def test_denied_api_calls_are_audited(env):
    client, _, _, audit, _ = env
    client.get("/api/v1/commercial/audit", headers=bearer("tok-trader"))
    denied = [e for e in audit.events() if e.outcome == "DENIED"]
    assert denied and denied[-1].actor_id == "trader-01" and denied[-1].action == "API:commercial_view_audit"


def test_default_superuser_session_has_no_commercial_access(env, monkeypatch):
    from backend.app.auth.token_store import token_store

    client, recon, controls, audit, _ = env
    token = token_store.create_session(username="admin", roles=["superuser"], minutes=5)
    app = FastAPI()
    app.router.routes.extend(create_commercial_governance_router(
        controls=controls, reconciliation=recon, collections=CollectionRepository(env[4]),
        history=CollectionHistoryRepository(env[4]), audit=audit, session_resolver=token_store_session_resolver,
    ).routes)
    real = TestClient(app)
    try:
        assert real.get("/api/v1/commercial/reconciliation/exceptions", headers=bearer(token)).status_code == 403
        assert real.get("/api/v1/commercial/reconciliation/exceptions", headers=bearer("not-a-session")).status_code == 401
    finally:
        token_store.revoke(token)


def test_router_exposes_no_money_movement_surface(env):
    client = env[0]
    routes = {(r.path, tuple(sorted(r.methods))) for r in client.app.routes if r.path.startswith("/api/v1/commercial")}
    assert len(routes) == len(ROUTES)
    forbidden = ("charge", "collect", "debit", "payout", "withdraw", "transfer", "execute", "order", "initiate", "settle")
    for path, methods in routes:
        assert set(methods) <= {"GET", "POST"}
        assert not any(word in path for word in forbidden), path


def test_web_app_mounts_governance_api_only_when_configured(tmp_path, monkeypatch):
    from dashboard.web.web_app import create_app

    monkeypatch.delenv("CSS_COMMERCIAL_DB", raising=False)
    plain = create_app()
    assert not any(getattr(r, "path", "").startswith("/api/v1/commercial/") for r in plain.routes)

    db = tmp_path / "configured.sqlite3"
    monkeypatch.setenv("CSS_COMMERCIAL_DB", str(db))
    client = TestClient(create_app())
    assert client.get("/api/v1/commercial/reconciliation/exceptions").status_code == 401
    assert client.get("/api/v1/commercial/audit", headers=bearer("forged")).status_code == 401
    assert db.exists()


def test_app_restart_preserves_pending_actions_and_resumes_interrupted_approvals(env, tmp_path, monkeypatch):
    from dashboard.web.web_app import create_app
    from engine.commercial.commercial_controls import ControlledActionStore

    _, recon, controls, audit, db = env
    monkeypatch.setenv("CSS_COMMERCIAL_DB", db)
    import dashboard.runtime.commercial_governance_router as router_module
    monkeypatch.setattr(router_module, "token_store_session_resolver", SESSIONS.get)

    first = TestClient(create_app())
    exception_id = first.get("/api/v1/commercial/reconciliation/exceptions", headers=bearer("tok-auditor")).json()["open_exceptions"][0]["exception_id"]
    pending = first.post(f"/api/v1/commercial/reconciliation/exceptions/{exception_id}/resolution-requests",
                         json={"resolution_reference": "ticket-9", "idempotency_key": "restart-1"}, headers=bearer("tok-maker")).json()["controlled_action"]

    # Process restart: the pending action is still there and still approvable.
    second = TestClient(create_app())
    listed = second.get("/api/v1/commercial/controlled-actions?status=PENDING", headers=bearer("tok-auditor")).json()["controlled_actions"]
    assert [a["action_id"] for a in listed] == [pending["action_id"]]

    # Crash between committing APPROVED and executing it.
    store = ControlledActionStore(db)
    assert store.transition(pending["action_id"], expected="PENDING", new="APPROVED", checker_id="head-fincon-01", checker_role="HEAD_FINCON")

    third = TestClient(create_app())  # mount-time resume
    done = third.get("/api/v1/commercial/controlled-actions?status=EXECUTED", headers=bearer("tok-auditor")).json()["controlled_actions"]
    assert [a["action_id"] for a in done] == [pending["action_id"]]
    assert third.get("/api/v1/commercial/reconciliation/exceptions", headers=bearer("tok-auditor")).json()["open_exceptions"] == []
    TestClient(create_app())  # a further restart must not execute it again
    executions = [e for e in CommercialAuditLog(db).events(object_id=pending["action_id"]) if e.action == "EXECUTE"]
    assert len(executions) == 1 and CommercialAuditLog(db).verify().ok
