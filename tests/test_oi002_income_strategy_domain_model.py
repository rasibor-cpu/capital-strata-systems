from __future__ import annotations

import inspect
import json

import pytest

import backend.options.options_income_strategy_domain as income_domain
from backend.options.option_payoff_engine import OptionPayoffEngine
from backend.options.option_risk_profile_engine import OptionRiskProfileEngine
from backend.options.options_income_strategy_domain import (
    build_cash_secured_put,
    build_covered_call,
)
from backend.options.options_strategy_engine import OptionStrategyEngine
from backend.trading.option_contract import CanonicalOptionContract


def _contract(option_type: str = "CALL", *, underlying: str = "SPY", strike: float = 105.0, multiplier: int = 100):
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": underlying,
            "option_symbol": f"{underlying}-20260821-{option_type[0]}-{int(strike)}",
            "expiration_date": "2026-08-21",
            "strike": strike,
            "option_type": option_type,
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 100,
            "open_interest": 500,
            "implied_volatility": 0.20,
            "delta": 0.35 if option_type == "CALL" else -0.35,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": 2.0,
            "probability_itm": 0.35,
            "exchange": "CBOE",
            "multiplier": multiplier,
            "currency": "USD",
            "timestamp": "2026-07-14T00:00:00+00:00",
        }
    )


def _covered_call(**overrides):
    payload = {
        "underlying_symbol": "SPY",
        "underlying_quantity": 100,
        "option_contract": _contract("CALL", strike=105),
        "short_call_quantity": 1,
        "premium_received": 2.0,
        "current_underlying_price": 100.0,
        "mode": "paper",
    }
    payload.update(overrides)
    return build_covered_call(**payload)


def _cash_secured_put(**overrides):
    payload = {
        "underlying_symbol": "SPY",
        "option_contract": _contract("PUT", strike=95),
        "short_put_quantity": 1,
        "premium_received": 2.0,
        "cash_collateral_available": 9500.0,
        "mode": "paper",
    }
    payload.update(overrides)
    return build_cash_secured_put(**payload)


class _MalformedContract:
    underlying_symbol = "SPY"
    option_symbol = "SPY-BAD"
    expiration_date = "not-a-date"
    strike = "not-a-number"
    option_type = "CALL"
    multiplier = "bad"


def test_covered_call_valid_model():
    model = _covered_call()

    assert model.valid is True
    assert model.validation_status == "PASS"
    assert model.to_dict()["strategy"] == "COVERED_CALL"
    assert model.option_contract is not None
    assert model.execution_allowed is False


def test_covered_call_exact_share_coverage():
    model = _covered_call(underlying_quantity=100, short_call_quantity=1)

    assert model.valid is True
    assert model.to_dict()["required_covered_quantity"] == 100.0


def test_covered_call_excess_share_coverage():
    model = _covered_call(underlying_quantity=150, short_call_quantity=1)

    assert model.valid is True
    assert model.to_dict()["underlying_quantity"] == 150.0


def test_covered_call_insufficient_share_coverage_rejected():
    model = _covered_call(underlying_quantity=99)

    assert model.valid is False
    assert "INSUFFICIENT_UNDERLYING_COVERAGE" in model.rejection_reasons


def test_covered_call_wrong_option_type_rejected():
    model = _covered_call(option_contract=_contract("PUT", strike=105))

    assert model.valid is False
    assert "OPTION_TYPE_MUST_BE_CALL" in model.rejection_reasons


def test_covered_call_underlying_mismatch_rejected():
    model = _covered_call(option_contract=_contract("CALL", underlying="QQQ", strike=105))

    assert model.valid is False
    assert "UNDERLYING_SYMBOL_MISMATCH" in model.rejection_reasons


def test_covered_call_zero_quantity_rejected():
    model = _covered_call(short_call_quantity=0)

    assert model.valid is False
    assert "INVALID_SHORT_CALL_QUANTITY" in model.rejection_reasons


def test_covered_call_negative_premium_rejected():
    model = _covered_call(premium_received=-0.01)

    assert model.valid is False
    assert "NEGATIVE_PREMIUM" in model.rejection_reasons


def test_covered_call_malformed_multiplier_rejected():
    bad = _MalformedContract()
    bad.expiration_date = "2026-08-21"
    bad.strike = 105
    bad.multiplier = 0
    model = _covered_call(option_contract=bad)

    assert model.valid is False
    assert "MALFORMED_MULTIPLIER" in model.rejection_reasons


def test_covered_call_correct_maximum_profit():
    model = _covered_call()

    assert model.to_dict()["maximum_profit"] == 700.0
    assert OptionPayoffEngine().calculate(model.to_dict())["max_profit"] == 700.0


def test_covered_call_correct_breakeven():
    model = _covered_call()

    assert model.to_dict()["breakeven"] == 98.0


def test_covered_call_capped_upside_representation():
    model = _covered_call()

    capped = model.to_dict()["capped_upside"]
    assert capped["capped"] is True
    assert capped["maximum_upside_per_share"] == 5.0
    assert capped["maximum_upside_total"] == 500.0


def test_covered_call_assignment_exposure():
    model = _covered_call()

    exposure = model.to_dict()["assignment_exposure"]
    assert exposure["assigned_underlying_quantity"] == 100.0
    assert exposure["assignment_sale_value"] == 10500.0


def test_covered_call_live_mode_rejected():
    model = _covered_call(mode="live")

    assert model.valid is False
    assert "UNSUPPORTED_LIVE_MODE" in model.rejection_reasons


def test_cash_secured_put_valid_model():
    model = _cash_secured_put()

    assert model.valid is True
    assert model.to_dict()["strategy"] == "CASH_SECURED_PUT"
    assert model.execution_allowed is False


def test_cash_secured_put_exact_collateral():
    model = _cash_secured_put(cash_collateral_available=9500)

    assert model.valid is True
    assert model.to_dict()["cash_collateral_required"] == 9500.0


def test_cash_secured_put_excess_collateral():
    model = _cash_secured_put(cash_collateral_available=12000)

    assert model.valid is True
    assert model.to_dict()["cash_collateral_available"] == 12000.0


def test_cash_secured_put_insufficient_collateral_rejected():
    model = _cash_secured_put(cash_collateral_available=9499.99)

    assert model.valid is False
    assert "INSUFFICIENT_CASH_COLLATERAL" in model.rejection_reasons


def test_cash_secured_put_missing_collateral_rejected():
    model = _cash_secured_put(cash_collateral_available=None)

    assert model.valid is False
    assert "MISSING_COLLATERAL_EVIDENCE" in model.rejection_reasons


def test_cash_secured_put_wrong_option_type_rejected():
    model = _cash_secured_put(option_contract=_contract("CALL", strike=95))

    assert model.valid is False
    assert "OPTION_TYPE_MUST_BE_PUT" in model.rejection_reasons


def test_cash_secured_put_underlying_mismatch_rejected():
    model = _cash_secured_put(option_contract=_contract("PUT", underlying="QQQ", strike=95))

    assert model.valid is False
    assert "UNDERLYING_SYMBOL_MISMATCH" in model.rejection_reasons


def test_cash_secured_put_zero_quantity_rejected():
    model = _cash_secured_put(short_put_quantity=0)

    assert model.valid is False
    assert "INVALID_SHORT_PUT_QUANTITY" in model.rejection_reasons


def test_cash_secured_put_negative_premium_rejected():
    model = _cash_secured_put(premium_received=-1)

    assert model.valid is False
    assert "NEGATIVE_PREMIUM" in model.rejection_reasons


def test_cash_secured_put_correct_maximum_profit():
    model = _cash_secured_put()

    assert model.to_dict()["maximum_profit"] == 200.0
    assert OptionPayoffEngine().calculate(model.to_dict())["max_profit"] == 200.0


def test_cash_secured_put_correct_breakeven():
    model = _cash_secured_put()

    assert model.to_dict()["breakeven"] == 93.0


def test_cash_secured_put_correct_assignment_cost_basis():
    model = _cash_secured_put()

    assert model.to_dict()["assignment_cost_basis"] == 93.0


def test_cash_secured_put_correct_downside_exposure():
    model = _cash_secured_put()

    assert model.to_dict()["downside_exposure"] == 9300.0
    assert model.to_dict()["maximum_loss"] == 9300.0


def test_cash_secured_put_live_mode_rejected():
    model = _cash_secured_put(mode="live")

    assert model.valid is False
    assert "UNSUPPORTED_LIVE_MODE" in model.rejection_reasons


def test_malformed_legs_fail_closed():
    covered = _covered_call(option_contract=_MalformedContract())
    csp = _cash_secured_put(option_contract=None)

    assert covered.valid is False
    assert csp.valid is False
    assert "MALFORMED_OPTION_CONTRACT" in covered.rejection_reasons
    assert "MISSING_OPTION_CONTRACT" in csp.rejection_reasons


def test_summaries_are_deterministic_and_serializable():
    first = _covered_call().to_dict()
    second = _covered_call().to_dict()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True))["strategy"] == "COVERED_CALL"


def test_safety_flags_remain_advisory_only():
    for payload in (_covered_call().to_dict(), _cash_secured_put().to_dict()):
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False
        assert payload["live_trading_blocked"] is True
        assert payload["broker_execution_armed"] is False


def test_no_broker_or_execution_imports_or_calls():
    source = inspect.getsource(income_domain)

    assert "backend.app.options.options_execution_adapter" not in source
    assert "execute_options_order" not in source
    assert "submit_order" not in source
    assert "place_order" not in source


def test_existing_long_call_behavior_remains_unchanged():
    chain = [{"option_type": "CALL", "strike": 100, "price": 4}, {"option_type": "CALL", "strike": 105, "price": 2}]
    strategy = OptionStrategyEngine().build_strategy(option_chain=chain, underlying_price=101, direction="CALL", tier="BASE")

    assert strategy == {
        "strategy": "LONG_CALL",
        "legs": [{"option_type": "CALL", "strike": 100, "price": 4}],
        "max_loss": 4,
        "max_profit": "UNLIMITED",
        "breakeven": 104,
    }
    assert OptionPayoffEngine().calculate(strategy)["max_profit"] == "UNLIMITED"


def test_existing_long_put_behavior_remains_unchanged():
    chain = [{"option_type": "PUT", "strike": 100, "price": 4}, {"option_type": "PUT", "strike": 95, "price": 2}]
    strategy = OptionStrategyEngine().build_strategy(option_chain=chain, underlying_price=99, direction="PUT", tier="BASE")

    assert strategy["strategy"] == "LONG_PUT"
    assert strategy["max_loss"] == 4
    assert strategy["breakeven"] == 96


def test_existing_debit_spread_behavior_remains_unchanged():
    chain = [
        {"option_type": "CALL", "strike": 100, "price": 2},
        {"option_type": "CALL", "strike": 105, "price": 1},
    ]
    strategy = OptionStrategyEngine().build_strategy(option_chain=chain, underlying_price=100, direction="CALL", tier="ELITE")

    assert strategy["strategy"] == "CALL_DEBIT_SPREAD"
    assert strategy["max_loss"] == 1
    assert strategy["max_profit"] == 4
    assert OptionRiskProfileEngine().evaluate(strategy)["strategy_risk_grade"] == "ELITE"
