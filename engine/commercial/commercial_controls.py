"""Durable maker-checker governance for controlled commercial actions.

A controlled action is proposed by a maker, approved or rejected by a different,
authorized checker, and executed exactly once after approval. Every state
change, and every denied attempt, is written to the append-only commercial
audit log. State lives in SQLite, so pending and approved actions survive a
process restart; ``resume_approved`` finishes any approval that was committed
but whose execution was interrupted.

Nothing here can move money, charge a customer, reach a payment provider or
touch broker execution. Executors registered for an action type operate only on
internal commercial records.
"""
import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from engine.commercial.commercial_audit import AuditOutcome, CommercialAuditLog
from engine.commercial.commercial_authorization import (
    CommercialActor,
    CommercialAuthorizationError,
    CommercialAuthorizer,
)

PREPARE_PERMISSION = "commercial_prepare_action"
APPROVE_PERMISSION = "commercial_approve_action"
OBJECT_TYPE = "commercial_controlled_action"


class ControlledActionStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"

    OPEN = (PENDING, APPROVED)


class ControlledActionError(ValueError):
    """A maker-checker rule was violated. Nothing was changed."""


class ControlledActionConflict(ControlledActionError):
    pass


@dataclass(frozen=True)
class ControlledAction:
    action_id: str
    action_type: str
    object_ref: str
    payload: Dict[str, Any]
    payload_hash: str
    idempotency_key: str
    maker_id: str
    maker_role: str
    requested_at: str
    status: str
    checker_id: Optional[str] = None
    checker_role: Optional[str] = None
    decided_at: Optional[str] = None
    decision_reason: Optional[str] = None
    evidence_ref: Optional[str] = None
    executed_at: Optional[str] = None
    resulting_state: Optional[str] = None
    failure_reason: Optional[str] = None


@dataclass(frozen=True)
class ControlledActionType:
    """Registered action: who may make/check it and what executing it does."""

    name: str
    execute: Callable[[ControlledAction], str]
    maker_permission: str = PREPARE_PERMISSION
    checker_permission: str = APPROVE_PERMISSION
    # Raises ValueError when the target object is not in a state this action
    # can act on. Run at request time and again immediately before approval.
    validate: Optional[Callable[[str, Dict[str, Any]], None]] = None


def payload_hash(action_type: str, object_ref: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps({"action_type": action_type, "object_ref": object_ref, "payload": payload}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlledActionStore:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        conn = self._connect()
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS commercial_controlled_actions (
                    action_id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    object_ref TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    maker_id TEXT NOT NULL,
                    maker_role TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    checker_id TEXT,
                    checker_role TEXT,
                    decided_at TEXT,
                    decision_reason TEXT,
                    evidence_ref TEXT,
                    executed_at TEXT,
                    resulting_state TEXT,
                    failure_reason TEXT
                )"""
            )
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS commercial_controlled_actions_one_open
                ON commercial_controlled_actions(action_type, object_ref)
                WHERE status IN ('PENDING', 'APPROVED')"""
            )
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _hydrate(row) -> ControlledAction:
        values = dict(row)
        values["payload"] = json.loads(values.pop("payload_json"))
        return ControlledAction(**values)

    def get(self, action_id: str) -> Optional[ControlledAction]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM commercial_controlled_actions WHERE action_id=?", (action_id,)).fetchone()
        finally:
            conn.close()
        return self._hydrate(row) if row else None

    def get_by_idempotency_key(self, key: str) -> Optional[ControlledAction]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM commercial_controlled_actions WHERE idempotency_key=?", (key,)).fetchone()
        finally:
            conn.close()
        return self._hydrate(row) if row else None

    def list(self, status: Optional[str] = None) -> List[ControlledAction]:
        conn = self._connect()
        try:
            if status is None:
                rows = conn.execute("SELECT * FROM commercial_controlled_actions ORDER BY requested_at, action_id").fetchall()
            else:
                rows = conn.execute("SELECT * FROM commercial_controlled_actions WHERE status=? ORDER BY requested_at, action_id", (status,)).fetchall()
        finally:
            conn.close()
        return [self._hydrate(r) for r in rows]

    def insert(self, action: ControlledAction) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO commercial_controlled_actions
                (action_id, action_type, object_ref, payload_json, payload_hash, idempotency_key,
                 maker_id, maker_role, requested_at, status, evidence_ref)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (action.action_id, action.action_type, action.object_ref,
                 json.dumps(action.payload, sort_keys=True, default=str), action.payload_hash,
                 action.idempotency_key, action.maker_id, action.maker_role, action.requested_at,
                 action.status, action.evidence_ref),
            )
        finally:
            conn.close()

    def transition(self, action_id: str, *, expected: str, new: str, **fields: Any) -> bool:
        """Compare-and-set the status. Returns False if another caller won the race."""
        assignments = ", ".join(f"{k}=?" for k in fields)
        sql = f"UPDATE commercial_controlled_actions SET status=?{', ' + assignments if assignments else ''} WHERE action_id=? AND status=?"
        conn = self._connect()
        try:
            cur = conn.execute(sql, (new, *fields.values(), action_id, expected))
            return cur.rowcount == 1
        finally:
            conn.close()


class CommercialControls:
    def __init__(
        self,
        store: ControlledActionStore,
        audit: CommercialAuditLog,
        authorizer: Optional[CommercialAuthorizer] = None,
        action_types: Optional[Dict[str, ControlledActionType]] = None,
    ):
        self.store = store
        self.audit = audit
        self.authorizer = authorizer or CommercialAuthorizer()
        self.action_types: Dict[str, ControlledActionType] = dict(action_types or {})

    def register(self, action_type: ControlledActionType) -> None:
        self.action_types[action_type.name] = action_type

    # -- helpers -----------------------------------------------------------

    def _authorize(self, actor, permission: str, *, audit_action: str, object_id: Optional[str], correlation_id: Optional[str]) -> CommercialActor:
        try:
            return self.authorizer.require(actor, permission)
        except CommercialAuthorizationError as exc:
            self.audit.append(
                action=audit_action, object_type=OBJECT_TYPE, object_id=object_id,
                outcome=AuditOutcome.DENIED, reason=exc.reason,
                actor_id=getattr(actor, "actor_id", None), actor_role=getattr(actor, "role", None),
                correlation_id=correlation_id,
            )
            raise

    def _refuse(self, message: str, *, audit_action: str, actor: CommercialActor, action: ControlledAction, correlation_id: Optional[str], conflict: bool = False):
        self.audit.append(
            action=audit_action, object_type=OBJECT_TYPE, object_id=action.action_id,
            outcome=AuditOutcome.REJECTED, reason=message, actor_id=actor.actor_id, actor_role=actor.role,
            previous_state=action.status, resulting_state=action.status, correlation_id=correlation_id,
            maker_id=action.maker_id, checker_id=action.checker_id, reference=action.object_ref,
        )
        raise (ControlledActionConflict if conflict else ControlledActionError)(message)

    def _type(self, name: str) -> ControlledActionType:
        if name not in self.action_types:
            raise ControlledActionError(f"unknown controlled action type: {name}")
        return self.action_types[name]

    # -- maker ---------------------------------------------------------------

    def request(
        self,
        actor: Optional[CommercialActor],
        *,
        action_type: str,
        object_ref: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        evidence_ref: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ControlledAction:
        spec = self._type(action_type)
        maker = self._authorize(actor, spec.maker_permission, audit_action="REQUEST", object_id=None, correlation_id=correlation_id)
        if not object_ref or not idempotency_key:
            raise ControlledActionError("object reference and idempotency key are required")
        digest = payload_hash(action_type, object_ref, payload)
        if spec.validate is not None:
            try:
                spec.validate(object_ref, payload)
            except ValueError as exc:
                self.audit.append(action="REQUEST", object_type=OBJECT_TYPE, outcome=AuditOutcome.REJECTED, reason=str(exc),
                                  actor_id=maker.actor_id, actor_role=maker.role, reference=object_ref, correlation_id=correlation_id)
                raise ControlledActionError(str(exc)) from exc

        existing = self.store.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if (existing.action_type, existing.object_ref, existing.payload_hash, existing.maker_id) != (action_type, object_ref, digest, maker.actor_id):
                raise ControlledActionConflict("idempotency key reused for a different controlled action")
            return existing

        action = ControlledAction(
            action_id=str(uuid.uuid4()), action_type=action_type, object_ref=object_ref,
            payload=dict(payload), payload_hash=digest, idempotency_key=idempotency_key,
            maker_id=maker.actor_id, maker_role=maker.role, requested_at=_now(),
            status=ControlledActionStatus.PENDING, evidence_ref=evidence_ref,
        )
        try:
            self.store.insert(action)
        except sqlite3.IntegrityError as exc:
            replay = self.store.get_by_idempotency_key(idempotency_key)
            if replay is not None and replay.payload_hash == digest and replay.maker_id == maker.actor_id:
                return replay
            raise ControlledActionConflict(f"an open {action_type} action already exists for {object_ref}") from exc
        self.audit.append(
            action="REQUEST", object_type=OBJECT_TYPE, object_id=action.action_id,
            outcome=AuditOutcome.SUCCEEDED, actor_id=maker.actor_id, actor_role=maker.role,
            resulting_state=action.status, maker_id=maker.actor_id, reference=object_ref,
            evidence_ref=evidence_ref, correlation_id=correlation_id,
            details={"action_type": action_type, "payload_hash": digest},
        )
        return action

    # -- checker -------------------------------------------------------------

    def _load_for_decision(self, checker: CommercialActor, action_id: str, audit_action: str, expected_payload_hash: str, correlation_id: Optional[str]) -> ControlledAction:
        action = self.store.get(action_id)
        if action is None:
            self.audit.append(action=audit_action, object_type=OBJECT_TYPE, object_id=action_id, outcome=AuditOutcome.REJECTED,
                              reason="unknown controlled action", actor_id=checker.actor_id, actor_role=checker.role, correlation_id=correlation_id)
            raise ControlledActionError("unknown controlled action")
        if action.maker_id == checker.actor_id:
            self._refuse("maker cannot check their own action", audit_action=audit_action, actor=checker, action=action, correlation_id=correlation_id)
        if action.status != ControlledActionStatus.PENDING:
            self._refuse(f"action is {action.status}, not PENDING", audit_action=audit_action, actor=checker, action=action, correlation_id=correlation_id, conflict=True)
        if not expected_payload_hash or expected_payload_hash != action.payload_hash:
            self._refuse("stale or manipulated approval: payload hash does not match", audit_action=audit_action, actor=checker, action=action, correlation_id=correlation_id)
        return action

    def approve(
        self,
        actor: Optional[CommercialActor],
        action_id: str,
        *,
        expected_payload_hash: str,
        evidence_ref: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ControlledAction:
        stored = self.store.get(action_id)
        spec = self._type(stored.action_type) if stored else None
        permission = spec.checker_permission if spec else APPROVE_PERMISSION
        checker = self._authorize(actor, permission, audit_action="APPROVE", object_id=action_id, correlation_id=correlation_id)
        action = self._load_for_decision(checker, action_id, "APPROVE", expected_payload_hash, correlation_id)
        if spec is not None and spec.validate is not None:
            try:
                spec.validate(action.object_ref, action.payload)
            except ValueError as exc:
                self._refuse(f"target is no longer in an approvable state: {exc}", audit_action="APPROVE", actor=checker, action=action, correlation_id=correlation_id, conflict=True)

        decided_at = _now()
        won = self.store.transition(
            action_id, expected=ControlledActionStatus.PENDING, new=ControlledActionStatus.APPROVED,
            checker_id=checker.actor_id, checker_role=checker.role, decided_at=decided_at,
            decision_reason=reason, evidence_ref=evidence_ref or action.evidence_ref,
        )
        if not won:
            current = self.store.get(action_id)
            self._refuse(f"action is {current.status}, not PENDING", audit_action="APPROVE", actor=checker, action=current, correlation_id=correlation_id, conflict=True)
        self.audit.append(
            action="APPROVE", object_type=OBJECT_TYPE, object_id=action_id, outcome=AuditOutcome.SUCCEEDED,
            actor_id=checker.actor_id, actor_role=checker.role, previous_state=ControlledActionStatus.PENDING,
            resulting_state=ControlledActionStatus.APPROVED, maker_id=action.maker_id, checker_id=checker.actor_id,
            reference=action.object_ref, evidence_ref=evidence_ref or action.evidence_ref, reason=reason,
            correlation_id=correlation_id,
        )
        return self._execute(self.store.get(action_id), correlation_id=correlation_id)

    def reject(
        self,
        actor: Optional[CommercialActor],
        action_id: str,
        *,
        expected_payload_hash: str,
        reason: str,
        correlation_id: Optional[str] = None,
    ) -> ControlledAction:
        stored = self.store.get(action_id)
        spec = self._type(stored.action_type) if stored else None
        permission = spec.checker_permission if spec else APPROVE_PERMISSION
        checker = self._authorize(actor, permission, audit_action="REJECT", object_id=action_id, correlation_id=correlation_id)
        if not reason:
            raise ControlledActionError("a rejection reason is required")
        action = self._load_for_decision(checker, action_id, "REJECT", expected_payload_hash, correlation_id)
        won = self.store.transition(
            action_id, expected=ControlledActionStatus.PENDING, new=ControlledActionStatus.REJECTED,
            checker_id=checker.actor_id, checker_role=checker.role, decided_at=_now(), decision_reason=reason,
        )
        if not won:
            current = self.store.get(action_id)
            self._refuse(f"action is {current.status}, not PENDING", audit_action="REJECT", actor=checker, action=current, correlation_id=correlation_id, conflict=True)
        self.audit.append(
            action="REJECT", object_type=OBJECT_TYPE, object_id=action_id, outcome=AuditOutcome.SUCCEEDED,
            actor_id=checker.actor_id, actor_role=checker.role, previous_state=ControlledActionStatus.PENDING,
            resulting_state=ControlledActionStatus.REJECTED, maker_id=action.maker_id, checker_id=checker.actor_id,
            reference=action.object_ref, reason=reason, correlation_id=correlation_id,
        )
        return self.store.get(action_id)

    # -- execution -----------------------------------------------------------

    def _execute(self, action: ControlledAction, *, correlation_id: Optional[str] = None) -> ControlledAction:
        if action.status != ControlledActionStatus.APPROVED:
            return action
        spec = self._type(action.action_type)
        try:
            resulting_state = spec.execute(action)
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
            if self.store.transition(action.action_id, expected=ControlledActionStatus.APPROVED, new=ControlledActionStatus.FAILED,
                                     executed_at=_now(), failure_reason=str(exc)):
                self.audit.append(
                    action="EXECUTE", object_type=OBJECT_TYPE, object_id=action.action_id, outcome=AuditOutcome.FAILED,
                    reason=str(exc), previous_state=ControlledActionStatus.APPROVED, resulting_state=ControlledActionStatus.FAILED,
                    maker_id=action.maker_id, checker_id=action.checker_id, reference=action.object_ref,
                    correlation_id=correlation_id,
                )
            return self.store.get(action.action_id)
        if self.store.transition(action.action_id, expected=ControlledActionStatus.APPROVED, new=ControlledActionStatus.EXECUTED,
                                 executed_at=_now(), resulting_state=resulting_state):
            self.audit.append(
                action="EXECUTE", object_type=OBJECT_TYPE, object_id=action.action_id, outcome=AuditOutcome.SUCCEEDED,
                previous_state=ControlledActionStatus.APPROVED, resulting_state=ControlledActionStatus.EXECUTED,
                maker_id=action.maker_id, checker_id=action.checker_id, reference=action.object_ref,
                evidence_ref=action.evidence_ref, correlation_id=correlation_id,
                details={"action_type": action.action_type, "object_resulting_state": resulting_state},
            )
        return self.store.get(action.action_id)

    def resume_approved(self) -> List[ControlledAction]:
        """Finish approvals committed before a crash. Executors must be idempotent."""
        return [self._execute(a) for a in self.store.list(ControlledActionStatus.APPROVED)]


# ---------------------------------------------------------------------------
# Controlled action: resolve a reconciliation exception
# ---------------------------------------------------------------------------

RESOLVE_RECONCILIATION_EXCEPTION = "RESOLVE_RECONCILIATION_EXCEPTION"


def reconciliation_resolution_action(reconciliation_service) -> ControlledActionType:
    """Resolution is proposed by one person and approved by another.

    The exception records the approving checker as ``resolved_by``; the maker is
    retained on the controlled action and in the audit log.
    """

    def execute(action: ControlledAction) -> str:
        reconciliation_service.resolve_exception(
            action.payload["exception_id"],
            resolved_by=action.checker_id,
            resolution_reference=action.payload["resolution_reference"],
        )
        return "RESOLVED"

    def validate(object_ref: str, payload: Dict[str, Any]) -> None:
        exception_id = payload.get("exception_id")
        if object_ref != f"reconciliation_exception:{exception_id}":
            raise ValueError("object reference does not match the exception")
        match = [e for e in reconciliation_service.exceptions.values() if e.exception_id == exception_id]
        if not match:
            raise ValueError(f"unknown reconciliation exception {exception_id}")
        if match[0].resolved_at is not None:
            raise ValueError(f"reconciliation exception {exception_id} is already resolved")

    return ControlledActionType(name=RESOLVE_RECONCILIATION_EXCEPTION, execute=execute, validate=validate)


def request_exception_resolution(controls: CommercialControls, actor, *, exception_id: str, resolution_reference: str,
                                 idempotency_key: str, evidence_ref: Optional[str] = None,
                                 correlation_id: Optional[str] = None) -> ControlledAction:
    if not exception_id or not resolution_reference:
        raise ControlledActionError("exception id and resolution reference are required")
    return controls.request(
        actor, action_type=RESOLVE_RECONCILIATION_EXCEPTION, object_ref=f"reconciliation_exception:{exception_id}",
        payload={"exception_id": exception_id, "resolution_reference": resolution_reference},
        idempotency_key=idempotency_key, evidence_ref=evidence_ref, correlation_id=correlation_id,
    )
