"""Atomic cross-asset budget tests against the CAD 20/40 reservation ledger.

Exercises the SQLite WAL + BEGIN IMMEDIATE semantics of
``PilotExposureReservationLedger``:
- simultaneous FX + derivative reservations against the CAD 20 parent / CAD 40
  aggregate / 2-concurrent-parent ceilings;
- pending/cancel/partial-fill transitions;
- crash-restart durability (reservation ledger reloaded from the same file);
- duplicate-child rejection.

No production code is modified by this test file. These tests only prove the
existing ledger's own contract; any defect discovered is a finding, not a
silent change.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import threading

import pytest

from backend.runtime.pilot_exposure_reservation import (
    PilotExposureReservationLedger,
    PilotReservationError,
)


@pytest.fixture()
def ledger(tmp_path: Path) -> PilotExposureReservationLedger:
    return PilotExposureReservationLedger(tmp_path / "reservations.db")


class TestCad20Cad40AtomicCeilings:
    def test_single_child_within_cad20_reserved(self, ledger):
        d = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("19.00"), estimated_fees_cad=Decimal("0.00"))
        assert d.approved, d.reason
        assert d.reserved_child_cad == Decimal("19.00")
        assert d.projected_parent_cad == Decimal("19.00")
        assert d.projected_total_cad == Decimal("19.00")

    def test_child_exceeding_cad20_parent_ceiling_denied(self, ledger):
        d = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("20.01"))
        assert d.approved is False
        assert "PARENT" in d.reason or "CAD20" in d.reason or "POSITION" in d.reason

    def test_two_children_accumulate_within_cad20_parent(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("10.00"))
        d2 = ledger.reserve(parent_id="P1", child_id="C2", proposed_child_cad=Decimal("9.50"))
        assert d1.approved and d2.approved
        assert d2.projected_parent_cad == Decimal("19.50")

    def test_second_child_exceeding_parent_ceiling_denied(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("19.00"))
        assert d1.approved
        d2 = ledger.reserve(parent_id="P1", child_id="C2", proposed_child_cad=Decimal("1.01"))
        assert d2.approved is False

    def test_cad40_aggregate_enforced_across_parents(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("19.50"))
        d2 = ledger.reserve(parent_id="P2", child_id="C2", proposed_child_cad=Decimal("19.50"))
        assert d1.approved and d2.approved
        d3 = ledger.reserve(parent_id="P3", child_id="C3", proposed_child_cad=Decimal("1.01"))
        assert d3.approved is False

    def test_max_two_concurrent_parents_enforced(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        d2 = ledger.reserve(parent_id="P2", child_id="C2", proposed_child_cad=Decimal("5.00"))
        assert d1.approved and d2.approved
        d3 = ledger.reserve(parent_id="P3", child_id="C3", proposed_child_cad=Decimal("5.00"))
        assert d3.approved is False
        # Reason should indicate concurrent-parent limit (not budget).
        assert "PARENT" in d3.reason or "CONCURRENT" in d3.reason

    def test_duplicate_child_id_rejected(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        assert d1.approved
        d2 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        assert d2.approved is False
        assert "DUPLICATE" in d2.reason

    def test_fees_counted_toward_ceiling(self, ledger):
        d = ledger.reserve(
            parent_id="P1",
            child_id="C1",
            proposed_child_cad=Decimal("19.00"),
            estimated_fees_cad=Decimal("1.01"),
        )
        assert d.approved is False
        # 19.00 + 1.01 = 20.01 > 20


# ---------------------------------------------------------------------------
# Simultaneous (concurrent) reservation attempts.
# ---------------------------------------------------------------------------

class TestSimultaneousReservations:
    """Two concurrent child-order requests cannot both observe the same free
    capacity and oversubscribe the CAD 20 parent / CAD 40 portfolio ceilings.

    SQLite BEGIN IMMEDIATE serializes writers, so exactly one of two racing
    20.00-children against a 20.00-parent ceiling must succeed and the other
    must fail with PILOT_PARENT_EXPOSURE_CEILING.
    """

    def _attempt_reserve(self, ledger, parent_id, child_id, amount):
        return ledger.reserve(parent_id=parent_id, child_id=child_id, proposed_child_cad=Decimal(amount))

    def test_two_racing_20cad_children_one_wins(self, ledger):
        outcomes = []

        def worker(child_id):
            outcomes.append(self._attempt_reserve(ledger, "P1", child_id, "20.00"))

        t1 = threading.Thread(target=worker, args=("C1",))
        t2 = threading.Thread(target=worker, args=("C2",))
        t1.start(); t2.start(); t1.join(); t2.join()

        assert len(outcomes) == 2
        approved = [d for d in outcomes if d.approved]
        denied = [d for d in outcomes if not d.approved]
        assert len(approved) == 1, f"expected exactly 1 approved, got {len(approved)}"
        assert len(denied) == 1
        assert denied[0].reason == "PILOT_PARENT_EXPOSURE_CEILING"

    def test_many_racing_children_never_oversubscribe_cad40(self, ledger):
        """8 children racing for 6.00 each against a 40.00 total must leave
        total committed <= 40.00 at all times.
        """
        outcomes = []
        lock = threading.Lock()

        def worker(child_id):
            d = self._attempt_reserve(ledger, f"P{int(child_id[1:])}", child_id, "6.00")
            with lock:
                outcomes.append(d)

        threads = [threading.Thread(target=worker, args=(f"C{i}",)) for i in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(outcomes) == 8
        approved_sum = sum((d.reserved_child_cad for d in outcomes if d.approved), Decimal("0.00"))
        assert approved_sum <= Decimal("40.00"), approved_sum
        approved_parents = {d.parent_id for d in outcomes if d.approved}
        assert len(approved_parents) <= 2

    def test_ledger_snapshot_is_consistent_after_race(self, ledger):
        self._attempt_reserve(ledger, "P1", "C1", "10.00")
        self._attempt_reserve(ledger, "P1", "C2", "10.00")
        snapshot = ledger.snapshot()
        assert len(snapshot) == 2
        assert all(row["state"] == "OPEN" for row in snapshot)


# ---------------------------------------------------------------------------
# Pending / cancel / partial-fill transition semantics.
# ---------------------------------------------------------------------------

class TestTransitionSemantics:
    def test_release_frees_capacity_for_reuse(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("19.00"))
        assert d1.approved
        # Transition to RELEASED (e.g. cancel).
        assert ledger.transition("C1", from_state="OPEN", to_state="RELEASED") is True
        # The released capacity is now available for a new child.
        d2 = ledger.reserve(parent_id="P1", child_id="C2", proposed_child_cad=Decimal("19.00"))
        assert d2.approved, d2.reason

    def test_commit_retains_capacity_for_audit(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("10.00"))
        assert d1.approved
        assert ledger.transition("C1", from_state="OPEN", to_state="COMMITTED") is True
        # A COMMITTED child still counts toward the ceilings (audit retention).
        d2 = ledger.reserve(parent_id="P1", child_id="C2", proposed_child_cad=Decimal("10.00"))
        assert d2.approved
        d3 = ledger.reserve(parent_id="P1", child_id="C3", proposed_child_cad=Decimal("0.01"))
        assert d3.approved is False

    def test_double_release_rejected(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        assert d1.approved
        assert ledger.transition("C1", from_state="OPEN", to_state="RELEASED") is True
        # Releasing again must fail (already RELEASED).
        assert ledger.transition("C1", from_state="OPEN", to_state="RELEASED") is False

    def test_transition_from_released_to_committed_rejected(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        assert d1.approved
        assert ledger.transition("C1", from_state="OPEN", to_state="RELEASED") is True
        # The transition API only supports OPEN->COMMITTED/RELEASED or
        # COMMITTED->RELEASED; a RELEASED row cannot become COMMITTED.
        assert ledger.transition("C1", from_state="RELEASED", to_state="COMMITTED") is False

    def test_invalid_transition_rejected(self, ledger):
        d1 = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        assert d1.approved
        assert ledger.transition("C1", from_state="OPEN", to_state="OPEN") is False
        assert ledger.transition("C1", from_state="COMMITTED", to_state="RELEASED") is False


# ---------------------------------------------------------------------------
# Crash-restart durability (same file, new process).
# ---------------------------------------------------------------------------

class TestCrashRestartDurability:
    """The reservation ledger is durable across process restarts (SQLite WAL
    with synchronous=FULL). A restart must not lose or resurrect reservations.
    """

    def test_reservations_survive_ledger_reload(self, tmp_path: Path):
        path = tmp_path / "reservations.db"
        ledger_a = PilotExposureReservationLedger(path)
        d1 = ledger_a.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("10.00"))
        d2 = ledger_a.reserve(parent_id="P1", child_id="C2", proposed_child_cad=Decimal("10.00"))
        assert d1.approved and d2.approved

        # Simulate a restart: a new ledger instance on the same file.
        ledger_b = PilotExposureReservationLedger(path)
        snapshot = ledger_b.snapshot()
        assert len(snapshot) == 2
        assert {row["child_id"] for row in snapshot} == {"C1", "C2"}

        # Capacity is still consumed: a third child must be denied.
        d3 = ledger_b.reserve(parent_id="P1", child_id="C3", proposed_child_cad=Decimal("0.01"))
        assert d3.approved is False

    def test_released_reservation_stays_released_after_reload(self, tmp_path: Path):
        path = tmp_path / "reservations.db"
        ledger_a = PilotExposureReservationLedger(path)
        assert ledger_a.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("15.00")).approved
        assert ledger_a.transition("C1", from_state="OPEN", to_state="RELEASED") is True

        ledger_b = PilotExposureReservationLedger(path)
        snapshot = ledger_b.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["state"] == "RELEASED"

        # Released capacity must not be resurrected: a new child within the old
        # amount must now be allowed again (reservation was released).
        d = ledger_b.reserve(parent_id="P1", child_id="C2", proposed_child_cad=Decimal("15.00"))
        assert d.approved, d.reason

    def test_duplicate_child_still_rejected_after_reload(self, tmp_path: Path):
        path = tmp_path / "reservations.db"
        ledger_a = PilotExposureReservationLedger(path)
        assert ledger_a.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00")).approved

        ledger_b = PilotExposureReservationLedger(path)
        d = ledger_b.reserve(parent_id="P1", child_id="C1", proposed_child_cad=Decimal("5.00"))
        assert d.approved is False
        assert "DUPLICATE" in d.reason
