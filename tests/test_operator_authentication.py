"""Operator web authentication.

Covers: salted password hashing (with legacy-hash upgrade on login), the
css_sign_on-backed operator login/logout/session-check endpoints, and that a
session's role -- always resolved server-side, never client-supplied --
correctly gates commercial-adjacent routes (trial enroll/cancel) via the same
bearer-session mechanism the commercial governance API already uses.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

import pytest
from fastapi import FastAPI

from tests.asgi_test_client import AsgiTestClient as TestClient

import backend.app.auth.operator_login_router as operator_login_router
import backend.app.auth.token_store as token_store_module
import dashboard.auth.css_sign_on as css_sign_on
from backend.app.auth.token_store import TokenStore
from dashboard.auth.css_sign_on import (
    authenticate_credentials,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from dashboard.runtime.commercial_governance_router import (
    commercial_controls_from_env,
    commercial_governance_router_from_env,
)
from dashboard.runtime.trial_contract_router import create_trial_contract_router

SUPER_USER_CTX = {"user_id": "00000", "role": "SUPER_USER"}

ENROLL_BODY = {
    "customer_id": "cust-1",
    "account_reference": "acct-1",
    "agreement_id": "agr-1",
    "agreement_version": "v1",
    "accepted_at": "2026-01-01T00:00:00Z",
    "displayed_pricing_summary": "summary",
    "displayed_conversion_disclosure": "disclosure",
    "acceptance_audit_reference": "audit-ref",
    "evidence_refs": ["ev-1"],
    "affirm_terms_acceptance": True,
    "affirm_automatic_conversion_disclosure": True,
    "idempotency_key": "enroll-key-1",
}
CANCEL_BODY = {
    "customer_id": "cust-1",
    "account_reference": "acct-1",
    "canceled_at": "2026-01-01T00:00:00Z",
    "cancellation_audit_reference": "audit-ref",
    "idempotency_key": "cancel-key-1",
    "evidence_refs": ["ev-1"],
}


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_password_is_salted_and_nondeterministic():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", first)
    assert verify_password("correct horse battery staple", second)


def test_verify_password_rejects_wrong_password():
    stored = hash_password("right-password")
    assert not verify_password("wrong-password", stored)
    assert not verify_password("", stored)


def test_legacy_unsalted_sha256_hash_still_verifies_and_flags_for_rehash():
    legacy = hashlib.sha256(b"legacy-password").hexdigest()
    assert verify_password("legacy-password", legacy)
    assert not verify_password("wrong-password", legacy)
    assert needs_password_rehash(legacy)
    assert not needs_password_rehash(hash_password("legacy-password"))


def _legacy_user_record(password: str) -> dict:
    from datetime import datetime

    return {
        "user_id": "00017",
        "display_name": "Legacy User",
        "role": "VIEWER",
        "unit_code": "CORE",
        "home_branch": "HQ",
        "password_hash": hashlib.sha256(password.encode("utf-8")).hexdigest(),
        "must_change_password": False,
        "last_password_change": datetime.now().isoformat(timespec="seconds"),
        "password_history": [],
        "failed_attempts": 0,
        "locked": False,
        "locked_at": None,
        "lockout_until": None,
        "lockout_seconds": 0,
        "lockout_started_at": None,
    }


def test_authenticate_credentials_upgrades_legacy_hash_on_successful_login():
    users = {"00017": _legacy_user_record("cssgood1")}
    authenticate_credentials(users, "00017", "cssgood1")
    assert users["00017"]["password_hash"].startswith("pbkdf2_sha256$")


def test_authenticate_credentials_does_not_upgrade_hash_on_failed_login():
    users = {"00017": _legacy_user_record("cssgood1")}
    with pytest.raises(css_sign_on.AuthFailure):
        authenticate_credentials(users, "00017", "wrong-password")
    assert not users["00017"]["password_hash"].startswith("pbkdf2_sha256$")


# ---------------------------------------------------------------------------
# Operator login router
# ---------------------------------------------------------------------------


@pytest.fixture
def operator_env(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    _real_load, _real_save = css_sign_on.load_users, css_sign_on.save_users
    # Accept an optional (ignored) users_file arg too: css_sign_on's own
    # internals (e.g. load_users' own "changed" auto-save) call these with an
    # explicit path positionally -- always route everything to the one temp file.
    patched_load = lambda *_a, **_k: _real_load(users_file)  # noqa: E731
    patched_save = lambda users, *_a, **_k: _real_save(users, users_file)  # noqa: E731

    # css_sign_on's own internal helpers (e.g. change_authenticated_password)
    # look up load_users/save_users as module globals at call time, so they
    # must be patched on the module itself, not just where this router
    # re-imported them.
    monkeypatch.setattr(css_sign_on, "load_users", patched_load)
    monkeypatch.setattr(css_sign_on, "save_users", patched_save)
    monkeypatch.setattr(operator_login_router, "load_users", patched_load)
    monkeypatch.setattr(operator_login_router, "save_users", patched_save)

    fresh_store = TokenStore()
    monkeypatch.setattr(token_store_module, "token_store", fresh_store)
    monkeypatch.setattr(operator_login_router, "token_store", fresh_store)

    users = _real_load(users_file)
    css_sign_on.create_user(
        users, SUPER_USER_CTX, "20001", "Test FinCon", "FINCON", "fincon-pass-1", must_change_password=False
    )
    css_sign_on.create_user(
        users, SUPER_USER_CTX, "20003", "Test Audit", "AUDIT", "audit-pass-1", must_change_password=False
    )
    # create_user always leaves last_password_change unset (forcing a change on
    # first login by design); simulate operators who already completed that
    # onboarding step so these fixtures exercise ordinary repeat sign-in.
    now = datetime.now().isoformat(timespec="seconds")
    users["20001"]["last_password_change"] = now
    users["20003"]["last_password_change"] = now
    css_sign_on.create_user(
        users, SUPER_USER_CTX, "20002", "Test Head FinCon", "HEAD_FINCON", "headfincon-pass-1", must_change_password=False
    )
    users["20002"]["last_password_change"] = now
    _real_save(users, users_file)

    commercial_env = {"CSS_COMMERCIAL_DB": str(tmp_path / "commercial.sqlite3")}
    controls = commercial_controls_from_env(commercial_env)
    governance_router = commercial_governance_router_from_env(commercial_env)

    app = FastAPI()
    app.router.routes.extend(operator_login_router.create_operator_login_router().routes)
    app.router.routes.extend(create_trial_contract_router(controls=controls).routes)
    app.router.routes.extend(governance_router.routes)
    client = TestClient(app)
    client.controls = controls
    return client


def _login(client, user_id, password):
    return client.post("/auth/operator/login", json={"user_id": user_id, "password": password})


def test_login_succeeds_and_resolves_real_role_from_the_store(operator_env):
    resp = _login(operator_env, "20001", "fincon-pass-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "20001"
    assert body["role"] == "FINCON"
    assert body["token"]


def test_client_supplied_role_field_is_ignored(operator_env):
    resp = operator_env.post(
        "/auth/operator/login",
        json={"user_id": "20001", "password": "fincon-pass-1", "role": "SUPER_USER"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "FINCON"


def test_login_rejects_wrong_password(operator_env):
    assert _login(operator_env, "20001", "wrong-password").status_code == 401


def test_login_rejects_unknown_user(operator_env):
    assert _login(operator_env, "99999", "whatever").status_code == 401


def test_repeated_failed_logins_lock_out_even_the_correct_password(operator_env):
    for _ in range(3):
        _login(operator_env, "20001", "wrong-password")
    assert _login(operator_env, "20001", "fincon-pass-1").status_code == 401


def test_me_requires_a_valid_session(operator_env):
    assert operator_env.get("/auth/operator/me").status_code == 401
    assert operator_env.get(
        "/auth/operator/me", headers={"Authorization": "Bearer forged-token"}
    ).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "just-a-token"}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer "}],
)
def test_malformed_authorization_headers_are_rejected(operator_env, headers):
    assert operator_env.get("/auth/operator/me", headers=headers).status_code == 401


def test_me_succeeds_with_a_freshly_issued_token(operator_env):
    token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    resp = operator_env.get("/auth/operator/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "20001"
    assert resp.json()["roles"] == ["FINCON"]


def test_logout_revokes_the_session(operator_env):
    token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    assert operator_env.get("/auth/operator/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    operator_env.post("/auth/operator/logout", headers={"Authorization": f"Bearer {token}"})
    assert operator_env.get("/auth/operator/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_newly_provisioned_operator_must_change_password_before_login_succeeds(operator_env):
    # operator_env has already patched load_users/save_users onto the shared
    # temp user store for this test, so these calls (no path argument) land there too.
    users = css_sign_on.load_users()
    css_sign_on.create_user(
        users, SUPER_USER_CTX, "20009", "Fresh Operator", "FINCON", "temp-initial-1"
    )
    css_sign_on.save_users(users)

    # First login attempt with the temporary password is rejected...
    assert _login(operator_env, "20009", "temp-initial-1").status_code == 401

    # ...but changing the password succeeds and immediately returns a usable session.
    resp = operator_env.post(
        "/auth/operator/change-password",
        json={
            "user_id": "20009",
            "current_password": "temp-initial-1",
            "new_password": "brand-new-pass-1",
            "confirm_password": "brand-new-pass-1",
        },
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    assert operator_env.get("/auth/operator/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    # And ordinary login now works too.
    assert _login(operator_env, "20009", "brand-new-pass-1").status_code == 200


def test_change_password_rejects_wrong_current_password(operator_env):
    users = css_sign_on.load_users()
    css_sign_on.create_user(users, SUPER_USER_CTX, "20010", "Another Operator", "AUDIT", "temp-initial-2")
    css_sign_on.save_users(users)

    resp = operator_env.post(
        "/auth/operator/change-password",
        json={
            "user_id": "20010",
            "current_password": "wrong-current",
            "new_password": "brand-new-pass-2",
            "confirm_password": "brand-new-pass-2",
        },
    )
    assert resp.status_code == 401


def test_tampered_token_is_rejected(operator_env):
    token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    tampered = (token[:-1] + ("a" if token[-1] != "a" else "b"))
    resp = operator_env.get("/auth/operator/me", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Trial contract router: closing the previously-unauthenticated routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/api/v1/commercial-trial/agreement?agreement_id=a&agreement_version=v", None),
        ("post", "/api/v1/commercial-trial/enroll", ENROLL_BODY),
        ("post", "/api/v1/commercial-trial/cancel", CANCEL_BODY),
        (
            "get",
            "/api/v1/commercial-trial/status"
            "?customer_id=c&account_reference=a&agreement_id=a&agreement_version=v&assessed_at=2026-01-01",
            None,
        ),
    ],
)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer forged-token"}])
def test_trial_routes_reject_missing_or_invalid_sessions(operator_env, method, path, body, headers):
    resp = getattr(operator_env, method)(path, headers=headers, **({"json": body} if body else {}))
    assert resp.status_code == 401


def test_trial_enroll_and_cancel_reject_a_valid_session_with_the_wrong_role(operator_env):
    audit_token = _login(operator_env, "20003", "audit-pass-1").json()["token"]
    headers = {"Authorization": f"Bearer {audit_token}"}
    assert operator_env.post("/api/v1/commercial-trial/enroll", json=ENROLL_BODY, headers=headers).status_code == 403
    assert operator_env.post("/api/v1/commercial-trial/cancel", json=CANCEL_BODY, headers=headers).status_code == 403


def test_trial_enroll_is_reachable_for_a_role_actually_granted_it(operator_env):
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    headers = {"Authorization": f"Bearer {fincon_token}"}
    resp = operator_env.post("/api/v1/commercial-trial/enroll", json=ENROLL_BODY, headers=headers)
    assert resp.status_code == 201
    action = resp.json()["controlled_action"]
    assert action["status"] == "PENDING"
    assert action["maker_id"] == "20001"
    assert action["maker_role"] == "FINCON"


# ---------------------------------------------------------------------------
# Trial maker-checker: enroll/cancel are proposed by one operator and executed
# only once a different, separately authorized operator approves -- reusing
# the same CommercialControls engine and the same generic
# /api/v1/commercial/controlled-actions/{id}/approve endpoint the
# reconciliation-exception flow already uses (no parallel subsystem).
# ---------------------------------------------------------------------------


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _prepare_enrollment(client, fincon_token, idempotency_key="enroll-key-1"):
    body = dict(ENROLL_BODY, idempotency_key=idempotency_key)
    resp = client.post("/api/v1/commercial-trial/enroll", json=body, headers=_bearer(fincon_token))
    assert resp.status_code == 201
    return resp.json()["controlled_action"]


def test_maker_cannot_approve_their_own_trial_enrollment(operator_env):
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    action = _prepare_enrollment(operator_env, fincon_token)

    resp = operator_env.post(
        f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
        json={"expected_payload_hash": action["payload_hash"]},
        headers=_bearer(fincon_token),
    )
    assert resp.status_code == 403


def test_wrong_role_cannot_approve_trial_enrollment(operator_env):
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    audit_token = _login(operator_env, "20003", "audit-pass-1").json()["token"]
    action = _prepare_enrollment(operator_env, fincon_token)

    resp = operator_env.post(
        f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
        json={"expected_payload_hash": action["payload_hash"]},
        headers=_bearer(audit_token),
    )
    assert resp.status_code == 403


def test_head_fincon_approval_transitions_the_action_exactly_once(operator_env):
    # This proves the maker-checker plumbing (approval authority, one-time
    # transition, checker recorded, no re-execution on replay). Whether the
    # underlying TrialContractEnrollmentService itself succeeds depends on a
    # real agreement being seeded there, which is that service's own concern
    # (and its own test coverage) -- EXECUTED and FAILED are both legitimate
    # terminal outcomes here; getting stuck at PENDING/APPROVED is not.
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    head_fincon_token = _login(operator_env, "20002", "headfincon-pass-1").json()["token"]
    action = _prepare_enrollment(operator_env, fincon_token)

    resp = operator_env.post(
        f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
        json={"expected_payload_hash": action["payload_hash"]},
        headers=_bearer(head_fincon_token),
    )
    assert resp.status_code == 200
    approved = resp.json()["controlled_action"]
    assert approved["status"] in ("EXECUTED", "FAILED")
    assert approved["checker_id"] == "20002"
    assert approved["checker_role"] == "HEAD_FINCON"

    # A second approval attempt on the now-terminal action is rejected, not re-executed.
    replay = operator_env.post(
        f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
        json={"expected_payload_hash": action["payload_hash"]},
        headers=_bearer(head_fincon_token),
    )
    assert replay.status_code == 409


def test_tampered_payload_hash_is_rejected_on_approval(operator_env):
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    head_fincon_token = _login(operator_env, "20002", "headfincon-pass-1").json()["token"]
    action = _prepare_enrollment(operator_env, fincon_token)

    resp = operator_env.post(
        f"/api/v1/commercial/controlled-actions/{action['action_id']}/approve",
        json={"expected_payload_hash": "0" * 64},
        headers=_bearer(head_fincon_token),
    )
    # Not an authorization failure (the checker IS permitted to approve) --
    # a stale/manipulated payload hash is a 422 per the shared ControlledActionError mapping.
    assert resp.status_code == 422


def test_duplicate_idempotency_key_replays_the_same_pending_action(operator_env):
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    first = _prepare_enrollment(operator_env, fincon_token, idempotency_key="same-key")
    second = _prepare_enrollment(operator_env, fincon_token, idempotency_key="same-key")
    assert first["action_id"] == second["action_id"]


def test_restart_preserves_pending_trial_action_for_approval(tmp_path, operator_env):
    fincon_token = _login(operator_env, "20001", "fincon-pass-1").json()["token"]
    action = _prepare_enrollment(operator_env, fincon_token, idempotency_key="restart-key")

    # Simulate a process restart: rebuild the controls engine from the same db.
    from dashboard.runtime.commercial_governance_router import commercial_controls_from_env

    commercial_env = {"CSS_COMMERCIAL_DB": operator_env.controls.store.db_path}
    rebuilt = commercial_controls_from_env(commercial_env)
    reloaded = rebuilt.store.get(action["action_id"])
    assert reloaded is not None
    assert reloaded.status == "PENDING"
