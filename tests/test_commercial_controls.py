"""RBAC, maker-checker and append-only audit for commercial controls.

Negative paths are the point: every test that grants something is paired with
the denials that must hold around it.
"""
import sqlite3
import threading
import time
from decimal import Decimal

import pytest

from backend.security.permissions import COMMERCIAL_ACTIONS, PermissionEngine
from engine.commercial.commercial_audit import AuditOutcome, CommercialAuditLog, GENESIS_HASH
from engine.commercial.commercial_authorization import (
    CommercialActor,
    CommercialAuthorizationError,
    CommercialAuthorizer,
)
from engine.commercial.commercial_controls import (
    CommercialControls,
    ControlledActionConflict,
    ControlledActionError,
    ControlledActionStatus,
    ControlledActionStore,
    ControlledActionType,
    RESOLVE_RECONCILIATION_EXCEPTION,
    reconciliation_resolution_action,
    request_exception_resolution,
)
from engine.commercial.reconciliation_repository import ReconciliationRepository
from engine.commercial.reconciliation_service import ReconciliationService, SettlementEvidence
from engine.domain.collections import CollectionStatus, CollectionTransaction

MAKER = CommercialActor("fincon-01", "FINCON")
CHECKER = CommercialActor("head-fincon-01", "HEAD_FINCON")
COMPLIANCE_CHECKER = CommercialActor("head-compliance-01", "HEAD_COMPLIANCE")
AUDITOR = CommercialActor("audit-01", "AUDIT")


# --- RBAC ------------------------------------------------------------------

@pytest.mark.parametrize("actor", [
    None,
    "HEAD_FINCON",
    CommercialActor("", "HEAD_FINCON"),
    CommercialActor("   ", "HEAD_FINCON"),
    CommercialActor("u1", ""),
    CommercialActor("u1", "NOT_A_ROLE"),
])
def test_missing_or_unknown_identity_and_role_fail_closed(actor):
    with pytest.raises(CommercialAuthorizationError):
        CommercialAuthorizer().require(actor, "commercial_view_collections")


def test_unknown_commercial_action_is_denied_even_for_privileged_roles():
    with pytest.raises(CommercialAuthorizationError):
        CommercialAuthorizer().require(CHECKER, "commercial_move_money")


@pytest.mark.parametrize("role", ["SUPER_USER", "ADMIN", "TECH", "HEAD_TECH", "TRADER", "TREASURY", "HEAD_TREASURY", "VIEWER", "TELLER", "OPERATIONS"])
def test_non_commercial_roles_have_no_commercial_rights(role):
    authorizer = CommercialAuthorizer()
    for action in COMMERCIAL_ACTIONS:
        assert not authorizer.allowed(CommercialActor("u", role), action), (role, action)


def test_least_privilege_matrix():
    a = CommercialAuthorizer()
    # Viewers cannot make or check.
    for viewer in (AUDITOR, CommercialActor("c", "COMPLIANCE")):
        assert a.allowed(viewer, "commercial_view_exceptions")
        assert not a.allowed(viewer, "commercial_prepare_action")
        assert not a.allowed(viewer, "commercial_approve_action")
    # FINCON makes but cannot check; heads check.
    assert a.allowed(MAKER, "commercial_prepare_action")
    assert not a.allowed(MAKER, "commercial_approve_action")
    assert a.allowed(CHECKER, "commercial_approve_action")
    assert a.allowed(COMPLIANCE_CHECKER, "commercial_approve_action")
    assert not a.allowed(COMPLIANCE_CHECKER, "commercial_prepare_action")
    # Audit history is not visible to plain FINCON or COMPLIANCE.
    assert not a.allowed(MAKER, "commercial_view_audit")
    assert a.allowed(AUDITOR, "commercial_view_audit")
    assert a.allowed(CHECKER, "commercial_administer_configuration")
    assert not a.allowed(MAKER, "commercial_administer_configuration")


def test_role_case_and_spacing_cannot_escalate_privilege():
    a = CommercialAuthorizer()
    assert not a.allowed(CommercialActor("u", "fincon admin"), "commercial_approve_action")
    assert not a.allowed(CommercialActor("u", "HEAD_FINCON;SUPER_USER"), "commercial_view_collections")


def test_commercial_grants_are_additive_to_existing_permissions():
    engine = PermissionEngine()
    assert engine.check("HEAD_FINCON", "close_period").allowed
    assert engine.check("TRADER", "submit_trade").allowed
    assert not engine.check("FINCON", "approve_trade").allowed


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "commercial.sqlite3")


def _exception_setup(db):
    repo = ReconciliationRepository(db)
    recon = ReconciliationService(repo)
    c = CollectionTransaction(
        obligation_id="obl-1", customer_id="cust-1", account_id="acct-1", amount=Decimal("25.00"),
        currency="CAD", idempotency_key="k-1", status=CollectionStatus.SETTLED, provider_reference="p-1",
        settlement_reference="s-1", ledger_txn_id="l-1",
    )
    recon.reconcile(c, SettlementEvidence(c.collection_id, "p-1", "s-1", Decimal("24.99"), "CAD"))
    return recon, recon.open_exceptions()[0]


def _controls(db, recon):
    controls = CommercialControls(ControlledActionStore(db), CommercialAuditLog(db))
    controls.register(reconciliation_resolution_action(recon))
    return controls


def _request(controls, exception_id, actor=MAKER, key="req-1", ref="ticket-7"):
    return request_exception_resolution(controls, actor, exception_id=exception_id, resolution_reference=ref, idempotency_key=key)


# --- maker-checker -----------------------------------------------------------

def test_maker_checker_resolves_exception_with_full_attribution(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    assert action.status == ControlledActionStatus.PENDING
    assert recon.open_exceptions(), "requesting must not resolve anything"

    done = controls.approve(CHECKER, action.action_id, expected_payload_hash=action.payload_hash, evidence_ref="bank-stmt-9")

    assert done.status == ControlledActionStatus.EXECUTED
    assert (done.maker_id, done.checker_id, done.resulting_state) == ("fincon-01", "head-fincon-01", "RESOLVED")
    assert done.decided_at and done.executed_at and done.evidence_ref == "bank-stmt-9"
    assert recon.open_exceptions() == []
    resolved = ReconciliationRepository(db).list_all()[0]
    assert resolved.resolved_by == "head-fincon-01" and resolved.resolution_reference == "ticket-7"


def test_self_approval_is_rejected_and_audited(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    self_checker = CommercialActor("head-fincon-01", "HEAD_FINCON")
    action = _request(controls, exc.exception_id, actor=self_checker)
    with pytest.raises(ControlledActionError, match="maker cannot check"):
        controls.approve(self_checker, action.action_id, expected_payload_hash=action.payload_hash)
    assert controls.store.get(action.action_id).status == ControlledActionStatus.PENDING
    assert recon.open_exceptions()
    assert controls.audit.events(object_id=action.action_id)[-1].outcome == AuditOutcome.REJECTED


def test_unauthorized_checker_and_maker_are_denied_and_audited(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    with pytest.raises(CommercialAuthorizationError):
        _request(controls, exc.exception_id, actor=AUDITOR)
    action = _request(controls, exc.exception_id)
    for bad in (None, AUDITOR, CommercialActor("fincon-02", "FINCON"), CommercialActor("x", "SUPER_USER")):
        with pytest.raises(CommercialAuthorizationError):
            controls.approve(bad, action.action_id, expected_payload_hash=action.payload_hash)
    assert controls.store.get(action.action_id).status == ControlledActionStatus.PENDING
    denied = [e for e in controls.audit.events() if e.outcome == AuditOutcome.DENIED]
    assert len(denied) == 5


def test_replayed_approval_is_rejected(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    controls.approve(CHECKER, action.action_id, expected_payload_hash=action.payload_hash)
    for again in (CHECKER, COMPLIANCE_CHECKER):
        with pytest.raises(ControlledActionConflict):
            controls.approve(again, action.action_id, expected_payload_hash=action.payload_hash)
    stored = controls.store.get(action.action_id)
    assert stored.checker_id == "head-fincon-01" and stored.status == ControlledActionStatus.EXECUTED


def test_stale_or_manipulated_approval_reference_is_rejected(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    tampered = action.payload_hash[:-1] + ("1" if action.payload_hash[-1] == "0" else "0")
    for bad_hash in ("", "0" * 64, tampered):
        with pytest.raises(ControlledActionError, match="payload hash"):
            controls.approve(CHECKER, action.action_id, expected_payload_hash=bad_hash)
    assert controls.store.get(action.action_id).status == ControlledActionStatus.PENDING


def test_approval_after_incompatible_state_change_is_rejected(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    recon.resolve_exception(exc.exception_id, resolved_by="someone-else", resolution_reference="other")
    with pytest.raises(ControlledActionConflict, match="no longer in an approvable state"):
        controls.approve(CHECKER, action.action_id, expected_payload_hash=action.payload_hash)
    assert controls.store.get(action.action_id).status == ControlledActionStatus.PENDING


def test_rejection_is_final_and_attributed(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    with pytest.raises(ControlledActionError):
        controls.reject(CHECKER, action.action_id, expected_payload_hash=action.payload_hash, reason="")
    rejected = controls.reject(CHECKER, action.action_id, expected_payload_hash=action.payload_hash, reason="evidence insufficient")
    assert (rejected.status, rejected.checker_id, rejected.decision_reason) == ("REJECTED", "head-fincon-01", "evidence insufficient")
    with pytest.raises(ControlledActionConflict):
        controls.approve(COMPLIANCE_CHECKER, action.action_id, expected_payload_hash=action.payload_hash)
    assert recon.open_exceptions()


def test_request_validation_and_idempotency(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    with pytest.raises(ControlledActionError, match="unknown reconciliation exception"):
        _request(controls, "no-such-exception", key="k-x")
    first = _request(controls, exc.exception_id)
    assert _request(controls, exc.exception_id).action_id == first.action_id
    with pytest.raises(ControlledActionConflict):
        _request(controls, exc.exception_id, ref="different-ticket")
    with pytest.raises(ControlledActionConflict, match="open"):
        _request(controls, exc.exception_id, key="req-2", ref="another")
    with pytest.raises(ControlledActionError):
        controls.request(MAKER, action_type="MOVE_MONEY", object_ref="x", payload={}, idempotency_key="z")


def test_concurrent_approvals_execute_exactly_once(db):
    recon, exc = _exception_setup(db)
    executions = []
    base = reconciliation_resolution_action(recon)

    def counting(action):
        executions.append(action.checker_id)
        return base.execute(action)

    def slow_validate(object_ref, payload):
        # Hold both checkers between reading PENDING and the state transition,
        # so only the compare-and-set can stop a double approval.
        base.validate(object_ref, payload)
        time.sleep(0.1)

    controls = CommercialControls(ControlledActionStore(db), CommercialAuditLog(db))
    controls.register(ControlledActionType(RESOLVE_RECONCILIATION_EXCEPTION, counting, validate=slow_validate))
    action = _request(controls, exc.exception_id)
    outcomes, barrier = [], threading.Barrier(2)

    def approve(checker):
        barrier.wait()
        try:
            outcomes.append(controls.approve(checker, action.action_id, expected_payload_hash=action.payload_hash))
        except (ControlledActionError, ValueError) as err:
            outcomes.append(err)

    threads = [threading.Thread(target=approve, args=(c,)) for c in (CHECKER, COMPLIANCE_CHECKER)]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    assert len(executions) == 1
    succeeded = [o for o in outcomes if not isinstance(o, Exception)]
    refused = [o for o in outcomes if isinstance(o, ControlledActionConflict)]
    assert len(succeeded) == 1 and len(refused) == 1, outcomes
    stored = controls.store.get(action.action_id)
    assert stored.status == ControlledActionStatus.EXECUTED
    assert stored.checker_id == succeeded[0].checker_id == executions[0]
    approvals = [e for e in controls.audit.events(object_id=action.action_id) if e.action == "APPROVE" and e.outcome == AuditOutcome.SUCCEEDED]
    assert len(approvals) == 1 and approvals[0].checker_id == stored.checker_id


def test_pending_action_survives_restart_and_can_be_approved(db):
    recon, exc = _exception_setup(db)
    action = _request(_controls(db, recon), exc.exception_id)

    restarted_recon = ReconciliationService(ReconciliationRepository(db))
    restarted = _controls(db, restarted_recon)
    pending = restarted.store.list(ControlledActionStatus.PENDING)
    assert [a.action_id for a in pending] == [action.action_id]
    done = restarted.approve(CHECKER, action.action_id, expected_payload_hash=pending[0].payload_hash)
    assert done.status == ControlledActionStatus.EXECUTED and restarted_recon.open_exceptions() == []


def test_approved_but_unexecuted_action_is_resumed_after_crash(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    # Simulate a crash between committing APPROVED and executing.
    assert controls.store.transition(action.action_id, expected="PENDING", new="APPROVED", checker_id=CHECKER.actor_id, checker_role=CHECKER.role)

    restarted_recon = ReconciliationService(ReconciliationRepository(db))
    restarted = _controls(db, restarted_recon)
    [resumed] = restarted.resume_approved()
    assert resumed.status == ControlledActionStatus.EXECUTED
    assert restarted_recon.open_exceptions() == []
    assert restarted.resume_approved() == []


# --- append-only audit -------------------------------------------------------

def test_audit_trail_records_the_full_lifecycle(db):
    recon, exc = _exception_setup(db)
    controls = _controls(db, recon)
    action = _request(controls, exc.exception_id)
    controls.approve(CHECKER, action.action_id, expected_payload_hash=action.payload_hash, evidence_ref="stmt-1")
    events = controls.audit.events(object_id=action.action_id)
    assert [(e.action, e.outcome, e.resulting_state) for e in events] == [
        ("REQUEST", "SUCCEEDED", "PENDING"), ("APPROVE", "SUCCEEDED", "APPROVED"), ("EXECUTE", "SUCCEEDED", "EXECUTED"),
    ]
    assert events[1].maker_id == "fincon-01" and events[1].checker_id == "head-fincon-01"
    assert events[1].evidence_ref == "stmt-1"
    assert controls.audit.verify().ok


def test_audit_events_cannot_be_updated_or_deleted(db):
    log = CommercialAuditLog(db)
    log.append(action="REQUEST", object_type="t", outcome=AuditOutcome.SUCCEEDED, actor_id="a")
    conn = sqlite3.connect(db)
    for sql in ("UPDATE commercial_audit_events SET actor_id='mallory'", "DELETE FROM commercial_audit_events"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute(sql)
    conn.close()
    assert not hasattr(log, "update") and not hasattr(log, "delete")
    assert log.events()[0].actor_id == "a"


def test_tampering_is_detected_by_hash_chain(db):
    log = CommercialAuditLog(db)
    for i in range(3):
        log.append(action=f"A{i}", object_type="t", outcome=AuditOutcome.SUCCEEDED, actor_id="a")
    assert log.verify().ok and log.verify().events_checked == 3
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER commercial_audit_events_no_update")
    conn.execute("UPDATE commercial_audit_events SET actor_id='mallory' WHERE seq=2")
    conn.commit()
    conn.close()
    result = log.verify()
    assert not result.ok and result.first_invalid_seq == 2


def test_audit_history_survives_restart_and_chain_continues(db):
    first = CommercialAuditLog(db)
    e1 = first.append(action="A", object_type="t", outcome=AuditOutcome.SUCCEEDED)
    assert e1.prev_hash == GENESIS_HASH
    restarted = CommercialAuditLog(db)
    e2 = restarted.append(action="B", object_type="t", outcome=AuditOutcome.SUCCEEDED)
    assert e2.prev_hash == e1.event_hash
    assert [e.action for e in restarted.events()] == ["A", "B"] and restarted.verify().ok


# --- external anchoring --------------------------------------------------------

def test_anchor_detects_consistent_chain_rebuild(tmp_path):
    from engine.commercial.commercial_audit import verify_against_anchors, write_anchor

    db = str(tmp_path / "audit.sqlite3")
    anchors = str(tmp_path / "anchors" / "audit_anchor.jsonl")
    log = CommercialAuditLog(db)
    for i in range(3):
        log.append(action=f"A{i}", object_type="t", outcome=AuditOutcome.SUCCEEDED, actor_id="alice")
    anchor = write_anchor(log, anchors)
    assert anchor.seq == 3 and verify_against_anchors(log, anchors).ok
    log.append(action="A3", object_type="t", outcome=AuditOutcome.SUCCEEDED)
    assert verify_against_anchors(log, anchors).ok, "appending after an anchor is legitimate"

    # An attacker with file access rebuilds a perfectly consistent chain.
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER commercial_audit_events_no_delete")
    conn.execute("DELETE FROM commercial_audit_events")
    conn.commit()
    conn.close()
    forged = CommercialAuditLog(db)
    for i in range(4):
        forged.append(action=f"A{i}", object_type="t", outcome=AuditOutcome.SUCCEEDED, actor_id="mallory")
    assert forged.verify().ok, "the rebuilt chain is internally consistent"
    result = verify_against_anchors(forged, anchors)
    assert not result.ok and result.anchor_seq == 3


def test_anchor_detects_truncation_and_refuses_to_bless_tampering(tmp_path):
    from engine.commercial.commercial_audit import verify_against_anchors, write_anchor

    db = str(tmp_path / "audit.sqlite3")
    anchors = str(tmp_path / "audit_anchor.jsonl")
    log = CommercialAuditLog(db)
    assert write_anchor(log, anchors) is None
    for i in range(2):
        log.append(action=f"A{i}", object_type="t", outcome=AuditOutcome.SUCCEEDED)
    write_anchor(log, anchors)
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER commercial_audit_events_no_update")
    conn.execute("UPDATE commercial_audit_events SET actor_id='mallory' WHERE seq=1")
    conn.commit()
    conn.close()
    assert not verify_against_anchors(log, anchors).ok
    with pytest.raises(ValueError, match="refusing to anchor"):
        write_anchor(log, anchors)


def test_anchor_detects_in_place_rewrite_with_recomputed_hashes(tmp_path):
    from dataclasses import asdict
    from engine.commercial.commercial_audit import GENESIS_HASH, _event_hash, verify_against_anchors, write_anchor

    db = str(tmp_path / "audit.sqlite3")
    anchors = str(tmp_path / "audit_anchor.jsonl")
    log = CommercialAuditLog(db)
    for i in range(3):
        log.append(action=f"A{i}", object_type="t", outcome=AuditOutcome.SUCCEEDED, actor_id="alice")
    write_anchor(log, anchors)

    # Rewrite seq 2's actor and recompute every hash: same seqs, same count,
    # internally consistent chain. Only the external anchor can tell.
    conn = sqlite3.connect(db)
    conn.execute("DROP TRIGGER commercial_audit_events_no_update")
    prev = GENESIS_HASH
    for event in log.events():
        content = asdict(event)
        if event.seq == 2:
            content["actor_id"] = "mallory"
        new_hash = _event_hash(prev, content)
        conn.execute("UPDATE commercial_audit_events SET actor_id=?, prev_hash=?, event_hash=? WHERE seq=?",
                     (content["actor_id"], prev, new_hash, event.seq))
        prev = new_hash
    conn.commit()
    conn.close()

    assert log.verify().ok and [e.seq for e in log.events()] == [1, 2, 3]
    result = verify_against_anchors(log, anchors)
    assert not result.ok and "rewritten" in result.problem
