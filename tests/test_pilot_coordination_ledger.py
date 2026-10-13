"""Authoritative pilot coordination ledger tests (CSS-062 Blockers 1, 5).

Blocker 1 — Reservation reconciliation:
- Legacy pilot_reservations preserved and counted.
- Mixed-version access (legacy + new writers).
- Concurrent reservations.
- Restart and reconciliation.
- Oversubscription (CAD 20/40/2-parent) never permitted.

Blocker 5 — Outcomes and crash consistency:
- Verifiable simulator evidence required (no caller-supplied strings).
- Unknown outcome preserves reservation.
- SQLite failure before commit → no state.
- SQLite failure after commit (commit-ack uncertainty) → durable state
  reconciled, NOT assumed denial.
- Duplicate/replay rejected.
- Legitimate no-fill release remains consistent.
- Never convert an uncertain committed reservation into an assumed denial.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
from backend.runtime.pilot_coordination_ledger import (
    AuthoritativePilotCoordinationLedger,
    CoordinationReceipt,
)
from backend.runtime.trusted_governed_paper_route import LocalSimulatorOutcomeEvidence

ISSUER_ID = "css-agent-trusted-issuer-001"
CANDIDATE_SHA = "a" * 40


@pytest.fixture
def config():
    return DEFAULT_ORDER_LIMIT_CONFIG


@pytest.fixture
def ledger(tmp_path: Path, config) -> AuthoritativePilotCoordinationLedger:
    return AuthoritativePilotCoordinationLedger(tmp_path / "coordination.db", config=config)


def _submit(
    ledger: AuthoritativePilotCoordinationLedger,
    *,
    approval_id: str,
    nonce: str,
    child_id: str,
    parent_id: str,
    proposed: str,
    fees: str = "0.00",
) -> CoordinationReceipt:
    return ledger.atomic_consume_and_reserve(
        approval_id=approval_id,
        nonce=nonce,
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        parent_id=parent_id,
        child_id=child_id,
        proposed_child_cad=proposed,
        estimated_fees_cad=fees,
    )


def _evidence_no_fill() -> LocalSimulatorOutcomeEvidence:
    return LocalSimulatorOutcomeEvidence(
        outcome="confirmed_no_fill",
        simulator_instance_id="sim-001",
        evidence_hash="abc123",
    )


def _evidence_fill() -> LocalSimulatorOutcomeEvidence:
    return LocalSimulatorOutcomeEvidence(
        outcome="confirmed_fill",
        simulator_instance_id="sim-001",
        evidence_hash="def456",
    )


# ============================================== BLOCKER 1: reconciliation
def test_legacy_reservations_reconciled_and_counted(tmp_path, config):
    """A legacy OPEN reservation must be counted by the new coordinator."""
    db_path = tmp_path / "coordination.db"
    # Seed a legacy reservation via a direct pilot_reservations insert.
    legacy = AuthoritativePilotCoordinationLedger(db_path, config=config)
    with legacy._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pilot_reservations (child_id, parent_id, reserved_cad, state) "
            "VALUES('legacy-c1', 'legacy-p1', '15.00', 'OPEN')"
        )
        conn.execute("COMMIT")

    # Reconcile: the legacy reservation must be counted.
    result = legacy.reconcile_legacy()
    assert result["failures"] == []
    assert result["created"] == 1

    # A new coordinated submission must count the legacy reservation.
    # Legacy: 15.00 on legacy-p1. New: 6.00 on legacy-p1 → 21 > 20 (parent ceiling).
    receipt = _submit(legacy, approval_id="A1", nonce="n1", child_id="c1", parent_id="legacy-p1", proposed="6.00")
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_PARENT_EXPOSURE_CEILING"


def test_legacy_and_new_writers_share_capacity_view(tmp_path, config):
    """Mixed-version access: legacy and new writers share the same capacity view."""
    db_path = tmp_path / "coordination.db"
    ledger = AuthoritativePilotCoordinationLedger(db_path, config=config)

    # New writer reserves 15 on p1.
    r1 = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00")
    assert r1.success is True

    # Legacy writer inserts directly into pilot_reservations (simulating a
    # concurrent old-version writer).
    with ledger._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pilot_reservations (child_id, parent_id, reserved_cad, state) "
            "VALUES('legacy-c2', 'p1', '5.00', 'OPEN')"
        )
        conn.execute("COMMIT")

    # New writer must see the legacy 5.00 and reject anything pushing p1 past 20.
    # p1 currently has 15 (new) + 5 (legacy) = 20. Any positive amount > 20.
    receipt = _submit(ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p1", proposed="1.00")
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_PARENT_EXPOSURE_CEILING"


def test_reconcile_legacy_idempotent(tmp_path, config):
    db_path = tmp_path / "coordination.db"
    ledger = AuthoritativePilotCoordinationLedger(db_path, config=config)
    with ledger._connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pilot_reservations (child_id, parent_id, reserved_cad, state) "
            "VALUES('legacy-c1', 'p1', '5.00', 'OPEN')"
        )
        conn.execute("COMMIT")

    first = ledger.reconcile_legacy()
    assert first["created"] == 1
    assert first["failures"] == []

    second = ledger.reconcile_legacy()
    assert second["created"] == 0
    assert second["skipped"] == 1
    assert second["failures"] == []


def test_concurrent_submissions_exactly_one_wins_same_nonce(tmp_path, config):
    db_path = tmp_path / "coordination.db"
    AuthoritativePilotCoordinationLedger(db_path, config=config)  # init schema

    def submit(thread_idx: int) -> CoordinationReceipt:
        local = AuthoritativePilotCoordinationLedger(db_path, config=config)
        return _submit(
            local,
            approval_id=f"A-{thread_idx}",
            nonce="same-nonce",
            child_id=f"c-{thread_idx}",
            parent_id="p1",
            proposed="5.00",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, i) for i in range(2)]
        results = [f.result() for f in futures]
    successes = [r for r in results if r.success]
    assert len(successes) == 1, f"expected 1 success, got {len(successes)}: {results}"


def test_concurrent_different_nonces_both_commit(tmp_path, config):
    db_path = tmp_path / "coordination.db"
    AuthoritativePilotCoordinationLedger(db_path, config=config)

    def submit(thread_idx: int) -> CoordinationReceipt:
        local = AuthoritativePilotCoordinationLedger(db_path, config=config)
        return _submit(
            local,
            approval_id=f"A-{thread_idx}",
            nonce=f"n-{thread_idx}",
            child_id=f"c-{thread_idx}",
            parent_id="p1",
            proposed="5.00",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, i) for i in range(2)]
        results = [f.result() for f in futures]
    assert all(r.success for r in results), results


def test_restart_recovers_committed_state(tmp_path, config):
    db_path = tmp_path / "coordination.db"
    ledger = AuthoritativePilotCoordinationLedger(db_path, config=config)
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    ledger.close()

    fresh = AuthoritativePilotCoordinationLedger(db_path, config=config)
    assert fresh.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True
    assert fresh.reservation_state(child_id="c1") == "OPEN"
    # Replay rejected after restart.
    receipt = _submit(fresh, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False


def test_cad_20_parent_ceiling_never_exceeded(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00")
    receipt = _submit(ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p1", proposed="6.00")
    # 15 + 6 = 21 > 20
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_PARENT_EXPOSURE_CEILING"


def test_cad_40_total_ceiling_never_exceeded(ledger):
    """Two parents at 15 each = 30 total; add 11 to p1 → 41 > 40 (but parent p1 = 26 > 20 first).

    Use two parents at 20 each = 40 total; any 3rd child triggers either
    the parent ceiling (p1 = 20 + x > 20) or the total ceiling (40 + x > 40).
    Test the TOTAL ceiling via a tighter config.
    """
    from backend.config.order_limit_config import CanonicalOrderLimitConfig

    tighter = CanonicalOrderLimitConfig(
        live_pilot_max_total_cad=Decimal("30.00"),
        live_pilot_max_position_cad=Decimal("20.00"),
        live_pilot_max_concurrent_positions=2,
    )
    tighter_ledger = AuthoritativePilotCoordinationLedger(
        ledger.path, config=tighter
    )
    _submit(tighter_ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00")
    _submit(tighter_ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p2", proposed="15.00")
    # 30 + 1 = 31 > 30 (TOTAL), p1 = 16 < 20 (parent OK).
    receipt = _submit(tighter_ledger, approval_id="A3", nonce="n3", child_id="c3", parent_id="p1", proposed="1.00")
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_TOTAL_EXPOSURE_CEILING"


def test_two_parent_ceiling_never_exceeded(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="5.00")
    _submit(ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p2", proposed="5.00")
    receipt = _submit(ledger, approval_id="A3", nonce="n3", child_id="c3", parent_id="p3", proposed="5.00")
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_CONCURRENT_PARENT_CEILING"


# =============================================== BLOCKER 5: outcomes
def test_caller_supplied_string_is_not_evidence(ledger):
    """A caller-supplied string is NOT verifiable simulator evidence."""
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    # Attempt to release with a string (not evidence).
    released = ledger.release_reservation(child_id="c1", reason="no_fill", confirmed_by_simulator="confirmed_no_fill")
    assert released is False
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_no_evidence_no_release(ledger):
    """No simulator evidence → the reservation is PRESERVED (fail closed)."""
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    released = ledger.release_reservation(child_id="c1", reason="no_fill", confirmed_by_simulator=None)
    assert released is False
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_verified_no_fill_evidence_releases(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    evidence = _evidence_no_fill()
    released = ledger.release_reservation(child_id="c1", reason="confirmed_no_fill", confirmed_by_simulator=evidence)
    assert released is True
    assert ledger.reservation_state(child_id="c1") == "RELEASED"
    # The nonce is still consumed (never reusable).
    assert ledger.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True


def test_verified_fill_evidence_commits(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    evidence = _evidence_fill()
    committed = ledger.commit_reservation(child_id="c1", confirmed_by_simulator=evidence)
    assert committed is True
    assert ledger.reservation_state(child_id="c1") == "COMMITTED"


def test_legitimate_release_remains_consistent(ledger):
    """A legitimate no-fill release must NOT be flagged as a desync."""
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    evidence = _evidence_no_fill()
    ledger.release_reservation(child_id="c1", reason="confirmed_no_fill", confirmed_by_simulator=evidence)
    result = ledger.verify_consistency()
    assert result["consistent"] is True
    assert result["problems"] == []


def test_nonce_never_reusable_even_after_release(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    evidence = _evidence_no_fill()
    ledger.release_reservation(child_id="c1", reason="confirmed_no_fill", confirmed_by_simulator=evidence)
    # Replay with the same nonce.
    receipt = _submit(ledger, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    assert "REPLAY" in receipt.reason or receipt.reason == "COORDINATION_REPLAY_REJECTED"


def test_duplicate_nonce_rejected(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    receipt = _submit(ledger, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False


def test_duplicate_child_rejected(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    receipt = _submit(ledger, approval_id="A2", nonce="n2", child_id="c1", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_DUPLICATE_CHILD_RESERVATION"


def test_duplicate_approval_id_rejected(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    receipt = _submit(ledger, approval_id="A1", nonce="n2", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False


# ======================================== BLOCKER 5: crash consistency
def test_sqlite_failure_before_commit_no_state(tmp_path, config, monkeypatch):
    """Simulate a SQLite failure BETWEEN BEGIN IMMEDIATE and COMMIT."""
    db_path = tmp_path / "coordination.db"
    ledger = AuthoritativePilotCoordinationLedger(db_path, config=config)

    class CrashingConnection:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper().startswith("COMMIT"):
                raise sqlite3.OperationalError("simulated crash before commit")
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __enter__(self):
            return self._inner.__enter__()

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    real_connect = ledger._connect
    monkeypatch.setattr(ledger, "_connect", lambda: CrashingConnection(real_connect()))

    receipt = _submit(ledger, approval_id="A-crash", nonce="n-crash", child_id="c-crash", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    monkeypatch.undo()

    fresh = AuthoritativePilotCoordinationLedger(db_path, config=config)
    assert fresh.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n-crash") is False
    assert fresh.reservation_state(child_id="c-crash") is None


def test_sqlite_failure_after_commit_reconciles_not_denies(tmp_path, config, monkeypatch):
    """A SQLite error AFTER a successful COMMIT must NOT be an assumed denial.

    The commit is durable. The coordination record exists. The route must
    reconcile via the durable state, not assume denial and not release.
    """
    db_path = tmp_path / "coordination.db"
    ledger = AuthoritativePilotCoordinationLedger(db_path, config=config)

    # Wrap the connection to raise on the SECOND COMMIT call (after the first
    # successful commit inside atomic_consume_and_reserve). We do this by
    # tracking a flag.
    commit_count = {"n": 0}
    real_connect = ledger._connect

    class DelayedCrashConnection:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper().startswith("COMMIT"):
                commit_count["n"] += 1
                if commit_count["n"] >= 2:
                    # The first COMMIT succeeded (durable); now raise on the
                    # acknowledgment path (simulating a post-commit error).
                    raise sqlite3.OperationalError("simulated post-commit failure")
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __enter__(self):
            return self._inner.__enter__()

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    # We need the FIRST commit to succeed and the SECOND to fail. The
    # atomic_consume_and_reserve does one BEGIN + one COMMIT. So we need a
    # wrapper that succeeds on the first COMMIT (the schema init) and fails
    # on the second (the atomic operation). Actually the schema init commits
    # separately. Let's count:
    # - _ensure_schema: BEGIN + COMMIT (1st COMMIT)
    # - atomic_consume_and_reserve: BEGIN + COMMIT (2nd COMMIT)
    # So we want the 2nd COMMIT to raise AFTER the inner commit succeeds.
    class PostCommitCrashConnection:
        def __init__(self, inner):
            self._inner = inner
            self._committed = False

        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper().startswith("COMMIT"):
                if self._committed:
                    # The inner COMMIT already succeeded (durable). Raise an
                    # error on the acknowledgment path.
                    raise sqlite3.OperationalError("simulated post-commit ack failure")
                self._inner.execute(sql, *args, **kwargs)
                self._committed = True
                # Raise AFTER the inner commit succeeded (durable).
                raise sqlite3.OperationalError("simulated post-commit ack failure")
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __enter__(self):
            return self._inner.__enter__()

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    # Use a fresh ledger so _ensure_schema's commit is the 1st.
    fresh_ledger = AuthoritativePilotCoordinationLedger(db_path, config=config)
    real_connect2 = fresh_ledger._connect
    # Reset the connection so the schema is already committed (fresh connect).
    # Now patch: the next atomic_consume_and_reserve's COMMIT raises after success.
    class PostCommitCrashConnection2:
        def __init__(self, inner):
            self._inner = inner
            self._in_atomic = False

        def execute(self, sql, *args, **kwargs):
            upper = sql.strip().upper()
            if upper.startswith("BEGIN IMMEDIATE"):
                self._in_atomic = True
            if upper.startswith("COMMIT") and self._in_atomic:
                # Perform the actual COMMIT (durable), then raise.
                result = self._inner.execute(sql, *args, **kwargs)
                raise sqlite3.OperationalError("simulated post-commit ack failure")
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __enter__(self):
            return self._inner.__enter__()

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    monkeypatch.setattr(fresh_ledger, "_connect", lambda: PostCommitCrashConnection2(real_connect2()))

    receipt = _submit(fresh_ledger, approval_id="A-post-commit", nonce="n-post-commit", child_id="c-post-commit", parent_id="p1", proposed="5.00")
    # The receipt must indicate the commit is durable (NOT a plain denial).
    assert receipt.success is True
    assert receipt.reason == "COORDINATION_COMMIT_ACK_UNCERTAIN"
    monkeypatch.undo()

    # Verify the durable state: both the nonce and the reservation survived.
    check = AuthoritativePilotCoordinationLedger(db_path, config=config)
    assert check.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n-post-commit") is True
    assert check.reservation_state(child_id="c-post-commit") == "OPEN"


def test_process_interruption_before_commit(tmp_path, config):
    """Abrupt process termination (SIGKILL) before COMMIT."""
    db_path = tmp_path / "coordination.db"
    AuthoritativePilotCoordinationLedger(db_path, config=config)  # init schema

    script = f"""
import sys, sqlite3, time
sys.path.insert(0, {str(Path.cwd())!r})
from backend.runtime.pilot_coordination_ledger import AuthoritativePilotCoordinationLedger
from backend.config.order_limit_config import DEFAULT_ORDER_LIMIT_CONFIG
ledger = AuthoritativePilotCoordinationLedger({str(db_path)!r}, config=DEFAULT_ORDER_LIMIT_CONFIG)
conn = ledger._connect()
conn.execute("BEGIN IMMEDIATE")
conn.execute(
    "INSERT INTO pilot_coordination (approval_id, nonce, issuer_id, candidate_sha, child_id, parent_id, reserved_cad, state, created_at, committed_at, schema_version) "
    "VALUES('A-interrupt', 'n-interrupt', '{ISSUER_ID}', '{CANDIDATE_SHA}', 'c-interrupt', 'p1', '5.00', 'COMMITTED', '2026-10-13T00:00:00Z', '2026-10-13T00:00:00Z', 2)"
)
conn.execute(
    "INSERT INTO pilot_reservations (child_id, parent_id, reserved_cad, state) "
    "VALUES('c-interrupt', 'p1', '5.00', 'OPEN')"
)
print("READY", flush=True)
time.sleep(30)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    line = proc.stdout.readline()
    assert "READY" in line, f"subprocess failed: {proc.stderr.read()}"
    proc.kill()
    proc.wait(timeout=5)

    fresh = AuthoritativePilotCoordinationLedger(db_path, config=config)
    assert fresh.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n-interrupt") is False
    assert fresh.reservation_state(child_id="c-interrupt") is None


# ================================================= invalid input
def test_nonpositive_amount_rejected(ledger):
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="0.00")
    assert receipt.success is False


def test_negative_fees_rejected(ledger):
    """Negative fees must NOT reduce the reserved exposure (Blocker 3)."""
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00", fees="-5.00")
    assert receipt.success is False


def test_invalid_decimal_rejected(ledger):
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="not-a-number")
    assert receipt.success is False


def test_non_finite_rejected(ledger):
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="inf")
    assert receipt.success is False


def test_missing_fields_rejected(ledger):
    receipt = ledger.atomic_consume_and_reserve(
        approval_id="",
        nonce="n1",
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        parent_id="p1",
        child_id="c1",
        proposed_child_cad="10.00",
        estimated_fees_cad="0.00",
    )
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_MISSING_FIELDS"
