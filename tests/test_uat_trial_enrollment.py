"""UAT seed agreement and a successful, fully governed trial enrollment end to end.

COM-015 engineering UAT showed maker-checker failing closed ("governing
commercial agreement is missing") on a clean runtime DB. This proves the
deterministic UAT seed (``scripts/seed_uat_trial_agreement.py``) and then the
whole governed path through the real web app: maker (cookie + CSRF, as the
page does) -> PENDING -> different authorized checker -> approval -> executed
-> persisted enrollment -> audit trail -> replay/duplicate protection, with
agreement validation left fully intact.
"""
from __future__ import annotations

import pytest

import backend.app.auth.token_store as token_store_module
from backend.app.auth.session_dependency import SESSION_COOKIE_NAME
from backend.app.auth.token_store import TokenStore
from backend.app.persistence import db
from dashboard.web.web_app import create_app
from engine.commercial.commercial_audit import CommercialAuditLog
from scripts import seed_uat_trial_agreement as seed_mod
from scripts.seed_uat_trial_agreement import UAT_AGREEMENT
from tests.asgi_test_client import AsgiTestClient as TestClient


@pytest.fixture
def runtime_db(tmp_path, monkeypatch):
    db.close_connection()
    path = tmp_path / "css_runtime.db"
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", path)  # restored after the test even though seed() reassigns it
    yield path
    db.close_connection()


# ---------------------------------------------------------------------------
# Seed script
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env", [None, "", "production", "prod"])
def test_seed_refuses_outside_development_or_uat(runtime_db, monkeypatch, env):
    if env is None:
        monkeypatch.delenv("CSS_ENV", raising=False)
    else:
        monkeypatch.setenv("CSS_ENV", env)
    with pytest.raises(RuntimeError, match="refusing"):
        seed_mod.seed(runtime_db)
    assert seed_mod.main(["--db", str(runtime_db)]) == 2


def test_seed_is_deterministic_and_idempotent(runtime_db, monkeypatch):
    monkeypatch.setenv("CSS_ENV", "development")
    assert seed_mod.seed(runtime_db) == "CREATED"
    assert seed_mod.seed(runtime_db) == "ALREADY_PRESENT"
    from backend.app.persistence.services.trial_contract_enrollment_service import TrialContractEnrollmentService

    loaded = TrialContractEnrollmentService().load_agreement(UAT_AGREEMENT.agreement_id, UAT_AGREEMENT.agreement_version)
    assert loaded == UAT_AGREEMENT
    assert loaded.pricing_summary.startswith("UAT ONLY")


def test_seed_never_rewrites_a_conflicting_agreement(runtime_db, monkeypatch):
    monkeypatch.setenv("CSS_ENV", "uat")
    from dataclasses import replace

    from backend.app.persistence.services.persistence_service import PersistenceService

    db.close_connection()
    PersistenceService().trial_contracts.create_agreement(replace(UAT_AGREEMENT, pricing_summary="different terms"))
    with pytest.raises(RuntimeError, match="append-only"):
        seed_mod.seed(runtime_db)


# ---------------------------------------------------------------------------
# End-to-end governed enrollment through the web app
# ---------------------------------------------------------------------------


@pytest.fixture
def env(runtime_db, tmp_path, monkeypatch):
    monkeypatch.setenv("CSS_ENV", "development")
    seed_mod.seed(runtime_db)
    store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", store)
    commercial_db = str(tmp_path / "commercial.sqlite3")
    monkeypatch.setenv("CSS_COMMERCIAL_DB", commercial_db)
    return TestClient(create_app()), store, commercial_db


def _cookie_csrf(store, user, role):
    token = store.create_session(user, [role])
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}", "X-CSRF-Token": store.validate(token).csrf_token}


def _bearer(store, user, role):
    return {"Authorization": f"Bearer {store.create_session(user, [role])}"}


def _enroll_body(customer="UAT-CUST-E2E", key="e2e-enroll-1", agreement=UAT_AGREEMENT):
    return {
        "customer_id": customer, "account_reference": "UAT-ACCT-E2E",
        "agreement_id": agreement.agreement_id, "agreement_version": agreement.agreement_version,
        "accepted_at": "2026-09-29T12:00:00Z",
        "displayed_pricing_summary": agreement.pricing_summary,
        "displayed_conversion_disclosure": agreement.automatic_conversion_disclosure,
        "acceptance_audit_reference": f"uat-accept-{key}", "evidence_refs": ["uat:e2e"],
        "affirm_terms_acceptance": True, "affirm_automatic_conversion_disclosure": True,
        "idempotency_key": key,
    }


def _approve(client, headers, action, payload_hash=None):
    return client.post(f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
                       json={"expected_payload_hash": payload_hash or action["payload_hash"]}, headers=headers)


def _persisted_enrollment(customer="UAT-CUST-E2E"):
    from backend.app.persistence.services.persistence_service import PersistenceService

    return PersistenceService().trial_contracts.get_enrollment(
        customer_id=customer, account_reference="UAT-ACCT-E2E",
        agreement_id=UAT_AGREEMENT.agreement_id, agreement_version=UAT_AGREEMENT.agreement_version,
    )


def test_successful_governed_trial_enrollment_end_to_end(env):
    client, store, commercial_db = env
    maker = _cookie_csrf(store, "10001", "FINCON")
    resp = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker)
    assert resp.status_code == 201, resp.content
    action = resp.json()["controlled_action"]
    assert action["status"] == "PENDING" and action["maker_id"] == "10001"
    assert _persisted_enrollment() is None  # nothing happens before approval

    # Idempotent re-submit returns the same pending action.
    again = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker)
    assert again.json()["controlled_action"]["action_id"] == action["action_id"]

    approved = _approve(client, _bearer(store, "10002", "HEAD_FINCON"), action)
    assert approved.status_code == 200, approved.content
    done = approved.json()["controlled_action"]
    assert done["status"] == "EXECUTED" and done["checker_id"] == "10002"
    assert done["resulting_state"].startswith("ENROLLED:2026-10-29")
    assert approved.json()["safety"]["execution_allowed"] is False

    row = _persisted_enrollment()
    assert row is not None and row["pricing_plan_id"] == UAT_AGREEMENT.pricing_plan_id
    assert row["trial_expires_at"] == "2026-10-29T12:00:00Z"

    # Replay of the approval is refused; the enrollment exists exactly once.
    assert _approve(client, _bearer(store, "10004", "HEAD_COMPLIANCE"), action).status_code == 409

    log = CommercialAuditLog(commercial_db)
    assert log.verify().ok
    lifecycle = [e.action for e in log.events(object_id=action["action_id"])]
    assert lifecycle[:3] == ["REQUEST", "APPROVE", "EXECUTE"]


def test_a_second_enrollment_for_the_same_customer_fails_closed(env):
    client, store, _ = env
    maker, checker = _cookie_csrf(store, "10001", "FINCON"), _bearer(store, "10002", "HEAD_FINCON")
    first = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker).json()["controlled_action"]
    assert _approve(client, checker, first).json()["controlled_action"]["status"] == "EXECUTED"
    second = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(key="e2e-enroll-dup"), headers=maker)
    assert second.status_code == 201
    result = _approve(client, checker, second.json()["controlled_action"]).json()["controlled_action"]
    assert result["status"] == "FAILED"  # the append-only enrollment is never duplicated or overwritten


@pytest.mark.parametrize("scenario", ["self_approval", "wrong_role", "tamper"])
def test_negative_approvals_leave_nothing_enrolled(env, scenario):
    client, store, _ = env
    if scenario == "self_approval":
        maker = _cookie_csrf(store, "10002", "HEAD_FINCON")  # HEAD_FINCON may both make and approve...
        action = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker).json()["controlled_action"]
        resp = _approve(client, _bearer(store, "10002", "HEAD_FINCON"), action)  # ...but never their own
    else:
        maker = _cookie_csrf(store, "10001", "FINCON")
        action = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker).json()["controlled_action"]
        if scenario == "wrong_role":
            resp = _approve(client, _bearer(store, "10003", "AUDIT"), action)
        else:
            resp = _approve(client, _bearer(store, "10002", "HEAD_FINCON"), action, payload_hash="0" * 64)
    assert resp.status_code in (403, 409, 422)
    assert _persisted_enrollment() is None


def test_unknown_agreement_still_fails_closed(env):
    from dataclasses import replace

    client, store, _ = env
    ghost = replace(UAT_AGREEMENT, agreement_id="NO-SUCH-AGREEMENT")
    action = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(agreement=ghost),
                         headers=_cookie_csrf(store, "10001", "FINCON")).json()["controlled_action"]
    result = _approve(client, _bearer(store, "10002", "HEAD_FINCON"), action).json()["controlled_action"]
    assert result["status"] == "FAILED" and "missing" in result["failure_reason"]


def test_displayed_terms_must_match_the_governing_agreement(env):
    client, store, _ = env
    body = _enroll_body()
    body["displayed_pricing_summary"] = "a cheaper price than the agreement says"
    action = client.post("/api/v1/commercial-trial/enroll", json=body,
                         headers=_cookie_csrf(store, "10001", "FINCON")).json()["controlled_action"]
    result = _approve(client, _bearer(store, "10002", "HEAD_FINCON"), action).json()["controlled_action"]
    assert result["status"] == "FAILED" and "pricing" in result["failure_reason"]
    assert _persisted_enrollment() is None


def test_governed_cancellation_executes_after_enrollment(env):
    client, store, _ = env
    maker, checker = _cookie_csrf(store, "10001", "FINCON"), _bearer(store, "10002", "HEAD_FINCON")
    enrolled = client.post("/api/v1/commercial-trial/enroll", json=_enroll_body(), headers=maker).json()["controlled_action"]
    assert _approve(client, checker, enrolled).json()["controlled_action"]["status"] == "EXECUTED"
    cancel = client.post("/api/v1/commercial-trial/cancel", headers=maker, json={
        "customer_id": "UAT-CUST-E2E", "account_reference": "UAT-ACCT-E2E", "canceled_at": "2026-10-05T00:00:00Z",
        "cancellation_audit_reference": "uat-cancel-e2e", "evidence_refs": ["uat:e2e"], "idempotency_key": "e2e-cancel-1",
    })
    assert cancel.status_code == 201 and cancel.json()["controlled_action"]["status"] == "PENDING"
    done = _approve(client, checker, cancel.json()["controlled_action"]).json()["controlled_action"]
    assert done["status"] == "EXECUTED" and done["resulting_state"] == "CANCELED"
    status = client.get(
        "/api/v1/commercial-trial/status?customer_id=UAT-CUST-E2E&account_reference=UAT-ACCT-E2E"
        f"&agreement_id={UAT_AGREEMENT.agreement_id}&agreement_version={UAT_AGREEMENT.agreement_version}"
        "&assessed_at=2026-10-06T00:00:00Z", headers={"Cookie": maker["Cookie"]})
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "CANCELED" and body["automatic_conversion_allowed"] is False
