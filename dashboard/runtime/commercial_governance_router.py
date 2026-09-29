"""Authenticated commercial governance API (read + maker-checker only).

Every route requires ``Authorization: Bearer <session token>``; the caller's
identity and roles come from the server-side session, never from the request
body or query. Authorization is enforced server-side through the commercial
RBAC grants, and the only state-changing routes create or decide controlled
maker-checker actions. No route can initiate a collection, charge a customer,
move money, reach a payment provider or touch broker execution, and every
response restates that fail-closed posture.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Optional, Sequence

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from engine.commercial.collection_history import CollectionHistoryRepository
from engine.commercial.collection_repository import CollectionRepository
from engine.commercial.commercial_audit import CommercialAuditLog
from engine.commercial.commercial_authorization import (
    CommercialActor,
    CommercialAuthorizationError,
    CommercialAuthorizer,
    actor_from_bearer,
)
from engine.commercial.commercial_controls import (
    CommercialControls,
    ControlledActionConflict,
    ControlledActionError,
    ControlledActionStatus,
    request_exception_resolution,
)
from engine.commercial.reconciliation_service import ReconciliationService
from engine.reporting.commercial_statements import build_statement

SAFETY_POSTURE = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
    "money_movement_allowed": False,
    "customer_charging_enabled": False,
}

# A session resolver returns (username, roles) for a valid token, or None.
SessionResolver = Callable[[str], Optional[tuple[str, Sequence[str]]]]


def token_store_session_resolver(token: str):
    from backend.app.auth.token_store import token_store

    info = token_store.validate(token)
    return None if info is None else (info.username, tuple(info.roles))


class ResolutionRequest(BaseModel):
    resolution_reference: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)
    evidence_ref: Optional[str] = Field(default=None, max_length=500)


class Decision(BaseModel):
    expected_payload_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    evidence_ref: Optional[str] = Field(default=None, max_length=500)
    reason: Optional[str] = Field(default=None, max_length=1000)


def _with_posture(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "safety": dict(SAFETY_POSTURE)}


def _action_view(action) -> dict[str, Any]:
    return asdict(action)


def create_commercial_governance_router(
    *,
    controls: CommercialControls,
    reconciliation: ReconciliationService,
    collections: CollectionRepository,
    history: CollectionHistoryRepository,
    audit: CommercialAuditLog,
    session_resolver: SessionResolver = token_store_session_resolver,
    authorizer: Optional[CommercialAuthorizer] = None,
) -> APIRouter:
    authorizer = authorizer or controls.authorizer
    router = APIRouter()

    def _log_denial(username: str, roles: Sequence[str], permission: str, reason: str) -> None:
        audit.append(action=f"API:{permission}", object_type="commercial_api", outcome="DENIED",
                     actor_id=username, actor_role=",".join(roles) or None, reason=reason)

    def actor_for(authorization: Optional[str], permission: str) -> CommercialActor:
        """Resolve the session and pick the caller's role that grants ``permission``."""
        return actor_from_bearer(
            authorization, permission,
            session_resolver=session_resolver, authorizer=authorizer, on_denied=_log_denial,
        )

    def decide(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CommercialAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=exc.reason) from exc
        except ControlledActionConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ControlledActionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/api/v1/commercial/safety-posture")
    def safety_posture(authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        actor_for(authorization, "commercial_view_reconciliation")
        return _with_posture({})

    @router.get("/api/v1/commercial/reconciliation/exceptions")
    def open_exceptions(authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        actor_for(authorization, "commercial_view_exceptions")
        items = sorted(reconciliation.open_exceptions(), key=lambda e: (e.created_at, e.exception_id))
        return _with_posture({"open_exceptions": [asdict(e) for e in items]})

    @router.post("/api/v1/commercial/reconciliation/exceptions/{exception_id}/resolution-requests", status_code=201)
    def request_resolution(exception_id: str, body: ResolutionRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        maker = actor_for(authorization, "commercial_prepare_action")
        action = decide(
            request_exception_resolution, controls, maker, exception_id=exception_id,
            resolution_reference=body.resolution_reference, idempotency_key=body.idempotency_key,
            evidence_ref=body.evidence_ref,
        )
        return _with_posture({"controlled_action": _action_view(action)})

    @router.get("/api/v1/commercial/controlled-actions")
    def list_actions(status: Optional[str] = Query(default=None), authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        actor_for(authorization, "commercial_view_exceptions")
        allowed = {ControlledActionStatus.PENDING, ControlledActionStatus.APPROVED, ControlledActionStatus.REJECTED,
                   ControlledActionStatus.EXECUTED, ControlledActionStatus.FAILED}
        if status is not None and status not in allowed:
            raise HTTPException(status_code=422, detail=f"unknown status {status}")
        return _with_posture({"controlled_actions": [_action_view(a) for a in controls.store.list(status)]})

    @router.post("/api/v1/commercial/controlled-actions/{action_id}/approve")
    def approve(action_id: str, body: Decision, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        checker = actor_for(authorization, "commercial_approve_action")
        action = decide(controls.approve, checker, action_id, expected_payload_hash=body.expected_payload_hash,
                        evidence_ref=body.evidence_ref, reason=body.reason)
        return _with_posture({"controlled_action": _action_view(action)})

    @router.post("/api/v1/commercial/controlled-actions/{action_id}/reject")
    def reject(action_id: str, body: Decision, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        checker = actor_for(authorization, "commercial_approve_action")
        action = decide(controls.reject, checker, action_id, expected_payload_hash=body.expected_payload_hash,
                        reason=body.reason or "")
        return _with_posture({"controlled_action": _action_view(action)})

    @router.get("/api/v1/commercial/customers/{customer_id}/statement")
    def statement(customer_id: str, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        actor_for(authorization, "commercial_view_statements")
        records = collections.list_for_customer(customer_id)
        open_ids = {e.collection_id for e in reconciliation.open_exceptions()}
        built = build_statement(customer_id, records, history=history, open_exception_collection_ids=open_ids)
        body = asdict(built)
        body["totals"] = {cur: {k: str(v) for k, v in vals.items()} for cur, vals in built.totals.items()}
        return _with_posture({"statement": body})

    @router.get("/api/v1/commercial/audit")
    def audit_trail(object_id: Optional[str] = Query(default=None), authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
        actor_for(authorization, "commercial_view_audit")
        verification = audit.verify()
        return _with_posture({
            "events": [asdict(e) for e in audit.events(object_id=object_id)],
            "chain_verified": verification.ok,
            "first_invalid_seq": verification.first_invalid_seq,
            "head_hash": audit.head_hash(),
            "integrity": "append-only + hash-chained (tamper-evident, not cryptographically immutable)",
        })

    return router


def _commercial_db_path(env=None) -> str:
    import os

    return (env if env is not None else os.environ).get("CSS_COMMERCIAL_DB", "").strip()


def commercial_controls_from_env(env=None) -> Optional[CommercialControls]:
    """Build (and register all known action types onto) the shared maker-checker
    engine when ``CSS_COMMERCIAL_DB`` names the commercial database, else None.

    Any caller building its own ``CommercialControls`` for the same db_path
    (e.g. the trial contract router) should go through this function instead
    of registering action types itself, so approving an action through the
    governance API's generic endpoints always finds the right executor --
    one action-type registry, reused, not duplicated per router.
    """
    db_path = _commercial_db_path(env)
    if not db_path:
        return None
    from engine.commercial.commercial_controls import (
        ControlledActionStore,
        reconciliation_resolution_action,
        trial_cancellation_action,
        trial_enrollment_action,
    )
    from engine.commercial.reconciliation_repository import ReconciliationRepository
    from backend.app.persistence.services.trial_contract_enrollment_service import (
        TrialContractEnrollmentService,
    )

    reconciliation = ReconciliationService(ReconciliationRepository(db_path))
    audit = CommercialAuditLog(db_path)
    controls = CommercialControls(ControlledActionStore(db_path), audit)
    controls.register(reconciliation_resolution_action(reconciliation))
    trial_service = TrialContractEnrollmentService()
    controls.register(trial_enrollment_action(trial_service))
    controls.register(trial_cancellation_action(trial_service))
    controls.resume_approved()
    return controls


def commercial_governance_router_from_env(env=None) -> Optional[APIRouter]:
    """Build the router when ``CSS_COMMERCIAL_DB`` names the commercial database.

    Returns None when unset, so the governance API is only exposed by explicit
    deployment configuration and never creates a database implicitly.
    """
    db_path = _commercial_db_path(env)
    if not db_path:
        return None
    controls = commercial_controls_from_env(env)
    audit = controls.audit
    from engine.commercial.reconciliation_repository import ReconciliationRepository
    reconciliation = ReconciliationService(ReconciliationRepository(db_path))
    return create_commercial_governance_router(
        controls=controls, reconciliation=reconciliation, collections=CollectionRepository(db_path),
        history=CollectionHistoryRepository(db_path), audit=audit,
        session_resolver=token_store_session_resolver,
    )
