from __future__ import annotations

import inspect
import json
from datetime import date, timedelta

import pytest

import backend.options.paper_income_lifecycle as lifecycle_module
from backend.options.collateral_manager import CollateralManager, CollateralManagerError
from backend.options.expiration_engine import ExpirationEngineError
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine, PaperIncomeLifecycleError
from backend.options.paper_position_repository import (
    PaperIncomePosition,
    PaperPositionRepository,
    PaperPositionRepositoryError,
    SAFE_FLAGS,
)
from backend.options.position_state_machine import (
    ACTIVE,
    APPROVED,
    ASSIGNED,
    CLOSED_EARLY,
    COMPLETED,
    DISCOVERED,
    EXERCISED,
    EXPIRING,
    EXPIRED_WORTHLESS,
    PAPER_OPEN,
    PositionStateMachine,
    PositionStateMachineError,
)
from backend.options.premium_accounting import PremiumAccounting, PremiumAccountingError
from backend.trading.option_contract import CanonicalOptionContract


AS_OF = date(2026, 7, 14)
ENTRY_DATE = AS_OF.isoformat()
EXPIRY = (AS_OF + timedelta(days=30)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _clock() -> str:
    return NOW


def _contract(option_type: str, *, strike: float | None = None, symbol: str | None = None) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": "SPY",
            "option_symbol": symbol or f"SPY-{EXPIRY}-{option_type[0]}-{int(strike)}",
            "expiration_date": EXPIRY,
            "strike": strike,
            "option_type": option_type,
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 100,
            "open_interest": 500,
            "implied_volatility": 0.20,
            "delta": 0.30 if option_type == "CALL" else -0.30,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": 2.0,
            "probability_itm": 0.30,
            "exchange": "CBOE",
            "multiplier": 100,
            "currency": "USD",
            "timestamp": NOW,
        }
    )


def _call_candidate():
    return IncomeOpportunityScanner().scan_covered_calls(
        [_contract("CALL")],
        underlying_symbol="SPY",
        underlying_price=100.0,
        underlying_quantity=100,
        as_of=AS_OF,
    )[0]


def _put_candidate():
    return IncomeOpportunityScanner().scan_cash_secured_puts(
        [_contract("PUT")],
        underlying_symbol="SPY",
        cash_collateral_available=9500.0,
        underlying_price=100.0,
        as_of=AS_OF,
    )[0]


def _engine(path=None) -> PaperIncomeLifecycleEngine:
    return PaperIncomeLifecycleEngine(repository=PaperPositionRepository(path), clock=_clock)


def _active_position(engine: PaperIncomeLifecycleEngine, candidate=None):
    position = engine.create_position(candidate or _call_candidate(), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)
    engine.open_position(position.position_id)
    return engine.activate_position(position.position_id)


def test_position_creation_from_covered_call_candidate():
    engine = _engine()

    position = engine.create_position(_call_candidate(), entry_date=ENTRY_DATE)

    assert position.current_state == DISCOVERED
    assert position.strategy_type == "COVERED_CALL"
    assert position.quantity == 100.0
    assert position.contracts == 1
    assert position.premium_received == 200.0
    assert position.premium_remaining == 200.0
    assert position.advisory_flags == SAFE_FLAGS
    assert position.lifecycle_events[0]["event_type"] == "Created"


def test_position_creation_from_cash_secured_put_candidate():
    engine = _engine()

    position = engine.create_position(_put_candidate(), entry_date=ENTRY_DATE)

    assert position.strategy_type == "CASH_SECURED_PUT"
    assert position.quantity == 100.0
    assert position.strike == 95.0
    assert position.option_symbol.endswith("P-95")


def test_premium_accounting_open_realize_and_close():
    accounting = PremiumAccounting()

    open_snapshot = accounting.open_snapshot(premium_received=200, collateral_reserved=10000, dte=30)
    realized = accounting.realize_all(premium_received=200, collateral_reserved=10000, dte=30)
    closed = accounting.close_early(premium_received=200, buyback_cost=75, collateral_reserved=10000, dte=30)

    assert open_snapshot.premium_remaining == 200.0
    assert realized.premium_realized == 200.0
    assert realized.premium_remaining == 0.0
    assert closed.premium_realized == 125.0
    assert closed.premium_remaining == 75.0
    assert realized.to_dict()["annualized_yield"] > 0


def test_premium_accounting_rejects_negative_values():
    with pytest.raises(PremiumAccountingError):
        PremiumAccounting().open_snapshot(premium_received=-0.01, collateral_reserved=100, dte=30)


def test_collateral_reservation_and_release_for_covered_call():
    engine = _engine()
    position = engine.create_position(_call_candidate(), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)

    opened = engine.open_position(position.position_id)
    record = engine.collateral.get(position.position_id)

    assert opened.current_state == PAPER_OPEN
    assert opened.collateral_reserved == 100.0
    assert record.collateral_type == "SHARES"
    assert record.amount_reserved == 100.0
    assert engine.collateral.release(position_id=position.position_id).amount_released == 100.0


def test_collateral_reservation_and_release_for_cash_secured_put():
    engine = _engine()
    position = engine.create_position(_put_candidate(), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)

    opened = engine.open_position(position.position_id)
    record = engine.collateral.release(position_id=position.position_id)

    assert opened.collateral_reserved == 9500.0
    assert record.collateral_type == "CASH"
    assert record.amount_released == 9500.0


def test_collateral_rejects_double_reservation_and_double_release():
    manager = CollateralManager()
    manager.reserve_cash(position_id="P1", cash=100)

    with pytest.raises(CollateralManagerError):
        manager.reserve_cash(position_id="P1", cash=100)

    manager.release(position_id="P1")
    with pytest.raises(CollateralManagerError):
        manager.release(position_id="P1")


def test_worthless_covered_call_expiration_completes():
    engine = _engine()
    active = _active_position(engine, _call_candidate())

    completed = engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY)

    assert completed.current_state == COMPLETED
    assert completed.assignment_status == EXPIRED_WORTHLESS
    assert completed.premium_realized == 200.0
    assert completed.premium_remaining == 0.0
    assert completed.collateral_released == 100.0


def test_assigned_covered_call_expiration_completes():
    engine = _engine()
    active = _active_position(engine, _call_candidate())

    completed = engine.process_expiration(active.position_id, underlying_price=110.0, as_of=EXPIRY)

    assert completed.current_state == COMPLETED
    assert completed.assignment_status == ASSIGNED
    assert "Assigned" in [event["event_type"] for event in completed.lifecycle_events]


def test_worthless_cash_secured_put_expiration_completes():
    engine = _engine()
    active = _active_position(engine, _put_candidate())

    completed = engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY)

    assert completed.current_state == COMPLETED
    assert completed.assignment_status == EXPIRED_WORTHLESS
    assert completed.collateral_released == 9500.0


def test_assigned_cash_secured_put_expiration_completes():
    engine = _engine()
    active = _active_position(engine, _put_candidate())

    completed = engine.process_expiration(active.position_id, underlying_price=90.0, as_of=EXPIRY)

    assert completed.current_state == COMPLETED
    assert completed.assignment_status == ASSIGNED
    assert completed.collateral_released == 9500.0


def test_closed_early_lifecycle_completes():
    engine = _engine()
    active = _active_position(engine, _call_candidate())

    completed = engine.close_early(active.position_id, buyback_cost=50.0, as_of=ENTRY_DATE)

    assert completed.current_state == COMPLETED
    assert completed.assignment_status == CLOSED_EARLY
    assert completed.premium_realized == 150.0
    assert completed.premium_remaining == 50.0


def test_forced_exercised_outcome_supported():
    engine = _engine()
    active = _active_position(engine, _call_candidate())

    completed = engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY, force_exercised=True)

    assert completed.current_state == COMPLETED
    assert completed.assignment_status == EXERCISED


def test_invalid_transitions_fail_closed():
    state_machine = PositionStateMachine()

    with pytest.raises(PositionStateMachineError):
        state_machine.transition(DISCOVERED, ACTIVE)
    with pytest.raises(PositionStateMachineError):
        state_machine.transition(COMPLETED, ACTIVE)


def test_lifecycle_methods_reject_invalid_sequence():
    engine = _engine()
    position = engine.create_position(_call_candidate(), entry_date=ENTRY_DATE)

    with pytest.raises(PaperIncomeLifecycleError):
        engine.open_position(position.position_id)


def test_duplicate_positions_are_rejected():
    engine = _engine()
    candidate = _call_candidate()
    engine.create_position(candidate, entry_date=ENTRY_DATE)

    with pytest.raises(PaperPositionRepositoryError):
        engine.create_position(candidate, entry_date=ENTRY_DATE)


def test_repository_recovery_from_disk(tmp_path):
    path = tmp_path / "positions.json"
    engine = _engine(path)
    created = engine.create_position(_call_candidate(), entry_date=ENTRY_DATE)

    recovered = PaperPositionRepository(path).get(created.position_id)

    assert recovered.to_dict() == created.to_dict()


def test_repository_corruption_fails_closed(tmp_path):
    path = tmp_path / "positions.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(PaperPositionRepositoryError):
        PaperPositionRepository(path)


def test_missing_candidate_or_strategy_rejected():
    engine = _engine()

    with pytest.raises(PaperIncomeLifecycleError):
        engine.create_position(None, entry_date=ENTRY_DATE)

    payload = _call_candidate().to_dict()
    payload["strategy_summary"] = {}
    with pytest.raises(PaperIncomeLifecycleError):
        engine.create_position(payload, entry_date=ENTRY_DATE)


def test_oi003_rejected_candidate_cannot_enter_lifecycle():
    engine = _engine()
    payload = _call_candidate().to_dict()
    payload["validation_status"] = "FAIL"

    with pytest.raises(PaperIncomeLifecycleError):
        engine.create_position(payload, entry_date=ENTRY_DATE)


def test_oi002_builder_summary_required():
    engine = _engine()
    payload = _put_candidate().to_dict()
    payload["strategy_summary"] = {"valid": False, "validation_status": "FAIL"}

    with pytest.raises(PaperIncomeLifecycleError):
        engine.create_position(payload, entry_date=ENTRY_DATE)


def test_event_history_is_ordered_and_json_serializable():
    engine = _engine()
    active = _active_position(engine, _call_candidate())
    completed = engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY)

    event_types = [event["event_type"] for event in completed.lifecycle_events]

    assert event_types == [
        "Created",
        "Approved",
        "Opened",
        "Premium Received",
        "Collateral Reserved",
        "Activated",
        "Expiration Processing Started",
        "Expiration Processed",
        "Expired Worthless",
        "Collateral Released",
        "Completed",
    ]
    assert json.loads(json.dumps(completed.to_dict(), sort_keys=True))["current_state"] == COMPLETED


def test_expiration_before_expiry_fails_closed():
    engine = _engine()
    active = _active_position(engine, _call_candidate())

    with pytest.raises(ExpirationEngineError):
        engine.process_expiration(active.position_id, underlying_price=100.0, as_of=ENTRY_DATE)


def test_completed_position_cannot_process_again():
    engine = _engine()
    active = _active_position(engine, _call_candidate())
    completed = engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY)

    with pytest.raises(PaperIncomeLifecycleError):
        engine.process_expiration(completed.position_id, underlying_price=100.0, as_of=EXPIRY)


def test_repository_rejects_negative_premium_and_collateral():
    bad = PaperIncomePosition(
        position_id="P1",
        strategy_id="COVERED_CALL",
        underlying="SPY",
        option_symbol="SPY-C",
        strategy_type="COVERED_CALL",
        quantity=100,
        contracts=1,
        entry_date=ENTRY_DATE,
        expiry=EXPIRY,
        strike=105,
        premium_received=-1,
        premium_realized=0,
        premium_remaining=0,
        collateral_reserved=0,
        collateral_released=0,
        current_state=DISCOVERED,
        assignment_status="NONE",
        lifecycle_events=[],
        timestamps={"created_at": NOW, "updated_at": NOW},
    )

    with pytest.raises(PaperPositionRepositoryError):
        PaperPositionRepository().add(bad)


def test_repository_rejects_unsafe_advisory_flags():
    payload = _call_candidate().to_dict()
    payload["execution_allowed"] = True

    with pytest.raises(PaperIncomeLifecycleError):
        _engine().create_position(payload, entry_date=ENTRY_DATE)


def test_invalid_timestamps_fail_closed():
    engine = _engine()
    position = engine.create_position(_call_candidate(), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)
    opened = engine.open_position(position.position_id)

    with pytest.raises(PaperPositionRepositoryError):
        PaperIncomePosition.from_dict({**opened.to_dict(), "entry_date": "not-a-date"})


def test_no_broker_or_execution_imports_or_calls():
    source = inspect.getsource(lifecycle_module)

    assert "options_execution_adapter" not in source
    assert "execute_options_order" not in source
    assert "submit_order" not in source
    assert "place_order" not in source


def test_safety_flags_remain_advisory_only_through_completed_lifecycle():
    engine = _engine()
    active = _active_position(engine, _put_candidate())
    completed = engine.process_expiration(active.position_id, underlying_price=100.0, as_of=EXPIRY)

    assert completed.advisory_flags == {
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }


def test_state_constants_cover_required_lifecycle():
    required = [
        DISCOVERED,
        APPROVED,
        PAPER_OPEN,
        ACTIVE,
        EXPIRING,
        EXPIRED_WORTHLESS,
        ASSIGNED,
        EXERCISED,
        CLOSED_EARLY,
        COMPLETED,
    ]

    assert required == [
        "DISCOVERED",
        "APPROVED",
        "PAPER_OPEN",
        "ACTIVE",
        "EXPIRING",
        "EXPIRED_WORTHLESS",
        "ASSIGNED",
        "EXERCISED",
        "CLOSED_EARLY",
        "COMPLETED",
    ]
