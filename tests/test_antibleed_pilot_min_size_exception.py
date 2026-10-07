import dataclasses
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import backend.runtime.pilot_min_size_exception as exc_mod
from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from backend.runtime.governed_pilot_profile import GovernedPilotProfile, sign_profile
from backend.runtime.pilot_authorization_ledger import PilotAuthorizationLedger
from backend.runtime.pilot_min_size_exception import (
    PilotMinSizeException, PilotMinSizeExceptionError, issue_pilot_min_size_exception,
)

KEY = b"k" * 32
SESSION = "proc-session-1"
GOOD = dict(expected_move_bps=80.0, fee_bps=5.0, spread_bps=5.0, slippage_bps=5.0)


@pytest.fixture
def guard(tmp_path):
    return AntiBleedGuard(state_file=str(tmp_path / "ab.json"))


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(exc_mod, "PILOT_MIN_SIZE_EXCEPTION_ENABLED", True)


def receipt_for(tmp_path, approval_id="change-001", instrument="ABC"):
    now = datetime.now(timezone.utc)
    p = GovernedPilotProfile.from_mapping({
        "approval_id": approval_id, "approver_id": "owner-1",
        "scope": "PILOT_PREFLIGHT_ONE_ORDER", "broker_id": "broker-a",
        "account_id": "acct-a", "asset_class": "EQUITY", "instrument": instrument,
        "currency": "CAD", "max_aggregate_exposure": "20.00",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "session_id": SESSION,
    })
    ledger = PilotAuthorizationLedger(tmp_path / "ledger")
    return ledger, ledger.consume(p, signature=sign_profile(p, KEY), signing_key=KEY, session_id=SESSION)


# ---- ordinary orders can never bypass the minimum-size control -------------

def test_default_is_disabled():
    assert exc_mod.PILOT_MIN_SIZE_EXCEPTION_ENABLED is False


def test_ordinary_small_order_still_rejected(guard):
    assert guard.evaluate("ABC", 20.0, **GOOD)["reason"] == "trade_size_too_small"


def test_minimum_unchanged_globally(guard):
    assert guard.minimum_profitable_trade_size == 50.0
    assert guard.evaluate("ABC", 50.0, **GOOD)["approved"]


@pytest.mark.parametrize("fake", [
    True, "PILOT", {"exception_id": "x"}, object(),
])
def test_arbitrary_values_cannot_bypass(guard, enabled, fake):
    assert guard.evaluate("ABC", 20.0, **GOOD, pilot_min_size_exception=fake)["reason"] == "trade_size_too_small"


def test_issue_refused_while_disabled(tmp_path):
    ledger, receipt = receipt_for(tmp_path)
    with pytest.raises(PilotMinSizeExceptionError):
        issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")


def test_capability_inert_when_disabled(tmp_path, guard, monkeypatch):
    monkeypatch.setattr(exc_mod, "PILOT_MIN_SIZE_EXCEPTION_ENABLED", True)
    ledger, receipt = receipt_for(tmp_path)
    cap = issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")
    monkeypatch.setattr(exc_mod, "PILOT_MIN_SIZE_EXCEPTION_ENABLED", False)
    assert not guard.evaluate("ABC", 20.0, **GOOD, pilot_min_size_exception=cap)["approved"]


# ---- the governed path, when explicitly enabled ----------------------------

def test_governed_exception_allows_exactly_one_pilot_order(tmp_path, guard, enabled):
    ledger, receipt = receipt_for(tmp_path)
    cap = issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")
    decision = guard.evaluate("ABC", 20.0, **GOOD, pilot_min_size_exception=cap)
    assert decision["approved"] and decision["pilot_min_size_exception_id"] == cap.exception_id
    # single use + cooldown recorded
    other = AntiBleedGuard(state_file=str(tmp_path / "ab2.json"))
    assert not other.evaluate("ABC", 20.0, **GOOD, pilot_min_size_exception=cap)["approved"]
    assert guard.evaluate("ABC", 60.0, **GOOD)["reason"] == "cooldown_active"


def test_one_capability_per_receipt(tmp_path, enabled):
    ledger, receipt = receipt_for(tmp_path)
    issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")
    with pytest.raises(PilotMinSizeExceptionError):
        issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")


def test_exception_does_not_relax_edge_cost_or_cooldown(tmp_path, guard, enabled):
    ledger, receipt = receipt_for(tmp_path)
    cap = issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")
    low_edge = dict(GOOD, expected_move_bps=30.0)
    assert guard.evaluate("ABC", 20.0, **low_edge, pilot_min_size_exception=cap)["reason"] == "insufficient_net_edge"
    below_cost = dict(GOOD, expected_move_bps=10.0)
    assert guard.evaluate("ABC", 20.0, **below_cost, pilot_min_size_exception=cap)["reason"] == "expected_move_below_cost"
    guard.evaluate("ABC", 60.0, **GOOD)  # starts cooldown
    assert not guard.evaluate("ABC", 20.0, **GOOD, pilot_min_size_exception=cap)["approved"]


def test_scope_size_and_expiry_bound(tmp_path, guard, enabled):
    ledger, receipt = receipt_for(tmp_path)
    cap = issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")
    assert not guard.evaluate("XYZ", 20.0, **GOOD, pilot_min_size_exception=cap)["approved"]
    assert not guard.evaluate("ABC", 20.01, **GOOD, pilot_min_size_exception=cap)["approved"]
    assert not guard.evaluate("ABC", 0.0, **GOOD, pilot_min_size_exception=cap)["approved"]
    assert not exc_mod.apply_pilot_min_size_exception(
        cap, symbol="ABC", trade_size=10, now=datetime.now(timezone.utc) + timedelta(minutes=5))
    with pytest.raises(PilotMinSizeExceptionError):
        issue_pilot_min_size_exception(ledger, receipt, symbol="ABC", ttl=timedelta(hours=1))


def test_forged_or_tampered_capability_rejected(tmp_path, guard, enabled):
    ledger, receipt = receipt_for(tmp_path)
    cap = issue_pilot_min_size_exception(ledger, receipt, symbol="ABC")
    widened = dataclasses.replace(cap, max_notional_cad=Decimal("49.99"))
    assert not guard.evaluate("ABC", 45.0, **GOOD, pilot_min_size_exception=widened)["approved"]
    forged = PilotMinSizeException("id", "h", "ABC", Decimal("20"), datetime.now(timezone.utc) + timedelta(minutes=1), "0" * 64)
    assert not guard.evaluate("ABC", 20.0, **GOOD, pilot_min_size_exception=forged)["approved"]


def test_unrecorded_receipt_or_wrong_symbol_cannot_issue(tmp_path, enabled):
    ledger, receipt = receipt_for(tmp_path)
    with pytest.raises(PilotMinSizeExceptionError):
        issue_pilot_min_size_exception(ledger, dataclasses.replace(receipt, entry_hash="f" * 64), symbol="ABC")
    with pytest.raises(PilotMinSizeExceptionError):
        issue_pilot_min_size_exception(ledger, receipt, symbol="XYZ")
