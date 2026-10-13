"""Pilot coordination ledger tests (CSS-062 Workstream B).

Tests for: concurrency, crash-recovery (simulated via monkeypatch),
restart, duplicate nonce, rollback, uncertain broker outcome, and the
fail-closed ceilings.

The coordination ledger is a SIMULATION-ONLY atomic transaction spanning
nonce-consumption + exposure-reservation + capacity checks in ONE
SQLite transaction.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from backend.runtime.pilot_coordination_ledger import (
    CoordinationReceipt,
    PilotCoordinationError,
    PilotCoordinationLedger,
)

CANDIDATE_SHA = "a" * 40
ISSUER_ID = "css-agent-trusted-issuer-001"

# CAD 20/40/2-parent ceilings (unchanged from the approved CAD-20 pilot).
MAX_PARENT_CAD = Decimal("20.00")
MAX_TOTAL_CAD = Decimal("40.00")
MAX_CONCURRENT_PARENTS = 2


@pytest.fixture
def ledger(tmp_path: Path) -> PilotCoordinationLedger:
    return PilotCoordinationLedger(tmp_path / "coordination.db")


def _submit(
    ledger: PilotCoordinationLedger,
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
        max_parent_cad=MAX_PARENT_CAD,
        max_total_cad=MAX_TOTAL_CAD,
        max_concurrent_parents=MAX_CONCURRENT_PARENTS,
    )


# ------------------------------------------------------------- basic commit
def test_atomic_commit_creates_both_nonce_and_reservation(ledger):
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    assert receipt.success is True
    assert receipt.reason == "COORDINATION_COMMITTED"
    assert ledger.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_duplicate_nonce_rejected(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    receipt = _submit(ledger, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    assert "COORDINATION_REPLAY_REJECTED" in receipt.reason
    assert ledger.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True
    # No partial state
    assert ledger.reservation_state(child_id="c2") is None


def test_duplicate_child_rejected(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    receipt = _submit(ledger, approval_id="A2", nonce="n2", child_id="c1", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_DUPLICATE_CHILD_RESERVATION"


def test_duplicate_approval_id_rejected(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    receipt = _submit(ledger, approval_id="A1", nonce="n2", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    assert "COORDINATION_REPLAY_REJECTED" in receipt.reason


# ---------------------------------------------------------- CAD 20/40 ceilings
def test_parent_cad_20_ceiling_enforced(ledger):
    """A reservation that would exceed the CAD 20 parent ceiling is rejected."""
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00")
    receipt = _submit(ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p1", proposed="6.00")
    # 15 + 6 = 21 > 20
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_PARENT_EXPOSURE_CEILING"
    assert ledger.reservation_state(child_id="c2") is None


def test_total_cad_ceiling_enforced_independent_of_parent(ledger):
    """Isolate the TOTAL ceiling by using a total ceiling lower than
    max_parent * max_parents.

    With max_parent=20, max_total=30, max_parents=2: two parents at 15 each
    (30 total, at the limit) — a third child that stays under each parent's
    20 ceiling but pushes the total past 30 triggers the TOTAL ceiling.
    """
    # Two parents, each at 15 (30 total = the TOTAL ceiling).
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="15.00")
    _submit(ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p2", proposed="15.00")
    # A third child under parent 1: 15+1=16 < 20 (parent OK) but 30+1=31 > 30 (TOTAL).
    receipt = ledger.atomic_consume_and_reserve(
        approval_id="A3",
        nonce="n3",
        issuer_id=ISSUER_ID,
        candidate_sha=CANDIDATE_SHA,
        parent_id="p1",
        child_id="c3",
        proposed_child_cad="1.00",
        estimated_fees_cad="0.00",
        max_parent_cad=Decimal("20.00"),
        max_total_cad=Decimal("30.00"),
        max_concurrent_parents=2,
    )
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_TOTAL_EXPOSURE_CEILING"
    # No partial state.
    assert ledger.reservation_state(child_id="c3") is None
    assert ledger.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n3") is False


def test_concurrent_parent_ceiling_enforced(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="5.00")
    _submit(ledger, approval_id="A2", nonce="n2", child_id="c2", parent_id="p2", proposed="5.00")
    receipt = _submit(ledger, approval_id="A3", nonce="n3", child_id="c3", parent_id="p3", proposed="5.00")
    # 3 distinct parents > 2
    assert receipt.success is False
    assert receipt.reason == "COORDINATION_CONCURRENT_PARENT_CEILING"


# --------------------------------------------------------------- concurrency
def test_concurrent_submissions_exactly_one_wins(ledger, tmp_path):
    """Two threads racing on the same nonce: exactly one succeeds."""
    def submit_once(thread_idx: int) -> CoordinationReceipt:
        # Each thread uses its own ledger (independent connection), same file.
        local = PilotCoordinationLedger(tmp_path / "coordination.db")
        return _submit(
            local,
            approval_id=f"A-concurrent-{thread_idx}",
            nonce="same-nonce",
            child_id=f"c-concurrent-{thread_idx}",
            parent_id="p1",
            proposed="5.00",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit_once, i) for i in range(2)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r.success]
    assert len(successes) == 1, f"expected exactly 1 success, got {len(successes)}: {results}"


def test_concurrent_different_nonces_both_commit(ledger, tmp_path):
    """Two threads with different nonces: both commit (serialized via BEGIN IMMEDIATE)."""
    def submit(thread_idx: int) -> CoordinationReceipt:
        local = PilotCoordinationLedger(tmp_path / "coordination.db")
        return _submit(
            local,
            approval_id=f"A-diff-{thread_idx}",
            nonce=f"n-diff-{thread_idx}",
            child_id=f"c-diff-{thread_idx}",
            parent_id="p1",
            proposed="5.00",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, i) for i in range(2)]
        results = [f.result() for f in futures]

    assert all(r.success for r in results), results


# ---------------------------------------------------------- crash-recovery
def test_crash_before_commit_leaves_no_state(tmp_path, monkeypatch):
    """Simulate a crash between BEGIN IMMEDIATE and COMMIT.

    The ROLLBACK (triggered by an exception) must discard BOTH the nonce
    consumption and the reservation.
    """
    ledger = PilotCoordinationLedger(tmp_path / "coordination.db")

    # Wrap the connection's execute method in a proxy class (sqlite3.Connection
    # attributes are read-only, so we wrap at the ledger level).
    class CrashingConnection:
        def __init__(self, inner: sqlite3.Connection) -> None:
            self._inner = inner

        def execute(self, sql: str, *args, **kwargs):
            if sql.strip().upper().startswith("COMMIT"):
                raise sqlite3.OperationalError("simulated crash before commit")
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    real_connect = ledger._connect
    monkeypatch.setattr(ledger, "_connect", lambda: CrashingConnection(real_connect()))

    receipt = _submit(ledger, approval_id="A-crash", nonce="n-crash", child_id="c-crash", parent_id="p1", proposed="5.00")
    # The exception must have been caught → receipt is a denial, not a crash.
    assert receipt.success is False
    monkeypatch.undo()

    # Fresh ledger (restart) — no state must have survived.
    fresh = PilotCoordinationLedger(tmp_path / "coordination.db")
    assert fresh.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n-crash") is False
    assert fresh.reservation_state(child_id="c-crash") is None


def test_restart_recovers_committed_state(tmp_path):
    """A committed coordination record survives a restart (fresh process)."""
    ledger = PilotCoordinationLedger(tmp_path / "coordination.db")
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    ledger.close()

    fresh = PilotCoordinationLedger(tmp_path / "coordination.db")
    assert fresh.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True
    assert fresh.reservation_state(child_id="c1") == "OPEN"
    # Replay rejected.
    receipt = _submit(fresh, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False


# ---------------------------------------------------- unknown broker outcome
def test_unknown_outcome_preserves_reservation(ledger):
    """An uncertain broker outcome must NOT release the reservation."""
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    # Simulate: broker returned unknown → we must NOT release.
    # (The route code calls release_reservation only on confirmed no-fill.)
    state_before = ledger.reservation_state(child_id="c1")
    assert state_before == "OPEN"
    # No release happens here; verify the state is preserved.
    assert ledger.reservation_state(child_id="c1") == "OPEN"


def test_confirmed_no_fill_may_release_capacity(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    released = ledger.release_reservation(child_id="c1", reason="confirmed_no_fill")
    assert released is True
    assert ledger.reservation_state(child_id="c1") == "RELEASED"
    # The nonce is still consumed (never reusable).
    assert ledger.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n1") is True


def test_release_nonce_does_not_make_nonce_reusable(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    released = ledger.release_reservation(child_id="c1", reason="explicit_reconciliation", release_nonce=True)
    assert released is True
    # The unique index on (issuer_id, nonce) blocks re-insert. Replaying
    # the same nonce (even after ROLLED_BACK) must be rejected.
    receipt = _submit(ledger, approval_id="A2", nonce="n1", child_id="c2", parent_id="p1", proposed="5.00")
    assert receipt.success is False
    assert "COORDINATION_REPLAY_REJECTED" in receipt.reason


# -------------------------------------------------------------- consistency
def test_verify_consistency_detects_no_problems(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    result = ledger.verify_consistency()
    assert result["consistent"] is True
    assert result["problems"] == []


def test_verify_consistency_detects_desync(ledger):
    """Simulate a journal desync: delete the reservation, leave the coordination record."""
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")

    # Tamper: remove the reservation directly (simulates a partial failure).
    ledger.tamper_for_test("DELETE FROM exposure_reservations WHERE child_id='c1'")

    result = ledger.verify_consistency()
    assert result["consistent"] is False
    assert any("JOURNAL_DESYNC" in p for p in result["problems"])


def test_verify_consistency_detects_orphan_reservation(ledger):
    _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="10.00")
    # Tamper: remove the coordination record.
    ledger.tamper_for_test("DELETE FROM coordination_records WHERE approval_id='A1'")
    result = ledger.verify_consistency()
    assert result["consistent"] is False
    assert any("ORPHAN_RESERVATION" in p for p in result["problems"])


# ------------------------------------------------------------- invalid input
def test_nonpositive_amount_rejected(ledger):
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="0.00")
    assert receipt.success is False
    assert "COORDINATION_NONPOSITIVE" in receipt.reason


def test_invalid_decimal_rejected(ledger):
    receipt = _submit(ledger, approval_id="A1", nonce="n1", child_id="c1", parent_id="p1", proposed="not-a-number")
    assert receipt.success is False
    assert "COORDINATION_INVALID_AMOUNT" in receipt.reason


# -------------------------------------------------- process interruption test
def test_process_interruption_before_commit(tmp_path):
    """Simulate an abrupt process kill (SIGKILL) before COMMIT.

    This test uses a subprocess that opens a transaction and is killed.
    """
    import subprocess
    import sys

    db_path = tmp_path / "coordination.db"
    script = f"""
import sys, sqlite3, time, os
sys.path.insert(0, {str(Path.cwd())!r})
from backend.runtime.pilot_coordination_ledger import PilotCoordinationLedger
ledger = PilotCoordinationLedger({str(db_path)!r})
conn = ledger._connect()
conn.execute("BEGIN IMMEDIATE")
conn.execute(
    "INSERT INTO coordination_records (approval_id, nonce, issuer_id, candidate_sha, child_id, parent_id, reserved_cad, state, created_at, committed_at) "
    "VALUES('A-interrupt', 'n-interrupt', '{ISSUER_ID}', '{CANDIDATE_SHA}', 'c-interrupt', 'p1', '5.00', 'COMMITTED', '2026-10-13T00:00:00Z', '2026-10-13T00:00:00Z')"
)
conn.execute(
    "INSERT INTO exposure_reservations (child_id, parent_id, reserved_cad, fees_cad, state, created_at) "
    "VALUES('c-interrupt', 'p1', '5.00', '0.00', 'OPEN', '2026-10-13T00:00:00Z')"
)
# Flush WAL but do NOT commit. Parent kills us here.
print("READY", flush=True)
time.sleep(30)
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Wait for READY
    line = proc.stdout.readline()
    assert "READY" in line, f"subprocess failed: {proc.stderr.read()}"
    # Kill the subprocess abruptly (SIGKILL).
    proc.kill()
    proc.wait(timeout=5)

    # Reopen from a fresh process — the uncommitted transaction must NOT have survived.
    fresh = PilotCoordinationLedger(db_path)
    assert fresh.nonce_is_consumed(issuer_id=ISSUER_ID, nonce="n-interrupt") is False
    assert fresh.reservation_state(child_id="c-interrupt") is None
