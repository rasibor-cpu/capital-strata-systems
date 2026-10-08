from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from backend.runtime.pilot_exposure_reservation import PilotExposureReservationLedger


def test_atomic_reservations_allow_only_two_cad20_parents(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "pilot.sqlite3")
    assert ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad="20.00").approved
    assert ledger.reserve(parent_id="P2", child_id="C2", proposed_child_cad="20.00").approved
    third = ledger.reserve(parent_id="P3", child_id="C3", proposed_child_cad="0.01")
    assert not third.approved
    assert third.reason in {"PILOT_CONCURRENT_EXPOSURE_CEILING", "PILOT_TOTAL_EXPOSURE_CEILING"}


def test_micro_children_share_same_parent_envelope(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "pilot.sqlite3")
    assert ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad="5.00").approved
    assert ledger.reserve(parent_id="P1", child_id="C2", proposed_child_cad="7.50").approved
    last = ledger.reserve(parent_id="P1", child_id="C3", proposed_child_cad="7.50")
    assert last.approved
    assert last.projected_parent_cad == Decimal("20.00")


def test_parent_cannot_exceed_cad20_even_by_one_cent(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "pilot.sqlite3")
    assert ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad="19.99").approved
    decision = ledger.reserve(parent_id="P1", child_id="C2", proposed_child_cad="0.02")
    assert not decision.approved
    assert decision.reason == "PILOT_PARENT_EXPOSURE_CEILING"


def test_duplicate_child_id_is_replay_blocked(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "pilot.sqlite3")
    assert ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad="5.00").approved
    replay = ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad="5.00")
    assert not replay.approved
    assert replay.reason == "PILOT_DUPLICATE_CHILD_RESERVATION"


def test_release_frees_capacity(tmp_path):
    ledger = PilotExposureReservationLedger(tmp_path / "pilot.sqlite3")
    assert ledger.reserve(parent_id="P1", child_id="C1", proposed_child_cad="20.00").approved
    assert ledger.transition("C1", from_state="OPEN", to_state="RELEASED")
    assert ledger.reserve(parent_id="P2", child_id="C2", proposed_child_cad="20.00").approved


def test_concurrent_reservations_cannot_oversubscribe_parent(tmp_path):
    path = tmp_path / "pilot.sqlite3"
    PilotExposureReservationLedger(path)

    def attempt(i: int):
        ledger = PilotExposureReservationLedger(path)
        return ledger.reserve(
            parent_id="P1",
            child_id=f"C{i}",
            proposed_child_cad="15.00",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(attempt, [1, 2]))

    assert sum(1 for d in decisions if d.approved) == 1
    assert any(d.reason == "PILOT_PARENT_EXPOSURE_CEILING" for d in decisions if not d.approved)
