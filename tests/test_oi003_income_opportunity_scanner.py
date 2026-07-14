from __future__ import annotations

import inspect
import json
from datetime import date, timedelta

import pytest

import backend.options.options_income_opportunity_scanner as scanner_module
from backend.options.options_income_opportunity_scanner import (
    IncomeOpportunityScanner,
    IncomeScannerConfig,
)
from backend.trading.option_contract import CanonicalOptionContract


AS_OF = date(2026, 7, 14)


def _contract(
    option_type: str,
    *,
    symbol: str | None = None,
    underlying: str = "SPY",
    strike: float | None = None,
    dte: int = 30,
    delta: float | None = None,
    bid: float = 1.9,
    ask: float = 2.1,
    midpoint: float | None = None,
    volume: int = 100,
    open_interest: int = 300,
    multiplier: int = 100,
) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
    midpoint = (bid + ask) / 2.0 if midpoint is None else midpoint
    delta = 0.30 if delta is None and option_type == "CALL" else (-0.30 if delta is None else delta)
    expiry = (AS_OF + timedelta(days=dte)).isoformat()
    option_symbol = symbol or f"{underlying}-{expiry}-{option_type[0]}-{strike}"
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": underlying,
            "option_symbol": option_symbol,
            "expiration_date": expiry,
            "strike": strike,
            "option_type": option_type,
            "bid": bid,
            "ask": ask,
            "midpoint": midpoint,
            "last": midpoint,
            "volume": volume,
            "open_interest": open_interest,
            "implied_volatility": 0.22,
            "delta": delta,
            "gamma": 0.02,
            "theta": -0.01,
            "vega": 0.10,
            "rho": 0.01,
            "intrinsic_value": 0.0,
            "extrinsic_value": midpoint,
            "probability_itm": abs(delta),
            "exchange": "CBOE",
            "multiplier": multiplier,
            "currency": "USD",
            "timestamp": "2026-07-14T00:00:00+00:00",
        }
    )


def _call_scan(contracts, **overrides):
    kwargs = {
        "underlying_symbol": "SPY",
        "underlying_price": 100.0,
        "underlying_quantity": 100,
        "as_of": AS_OF,
    }
    kwargs.update(overrides)
    return IncomeOpportunityScanner().scan_covered_calls(contracts, **kwargs)


def _call_scan_all(contracts, **overrides):
    return _call_scan(contracts, include_rejected=True, **overrides)


def _put_scan(contracts, **overrides):
    kwargs = {
        "underlying_symbol": "SPY",
        "cash_collateral_available": 9500.0,
        "underlying_price": 100.0,
        "as_of": AS_OF,
    }
    kwargs.update(overrides)
    return IncomeOpportunityScanner().scan_cash_secured_puts(contracts, **kwargs)


def _put_scan_all(contracts, **overrides):
    return _put_scan(contracts, include_rejected=True, **overrides)


def _bad_row(**overrides):
    row = _contract("CALL").to_dict()
    row.update(overrides)
    return row


def test_covered_call_valid_candidate_accepted():
    [candidate] = _call_scan([_contract("CALL")])

    assert candidate.strategy == "COVERED_CALL"
    assert candidate.valid is True
    assert candidate.strategy_summary["valid"] is True
    assert candidate.option_contract is not None


def test_covered_call_multiple_candidates_ranked_deterministically():
    rows = [_contract("CALL", symbol="B", midpoint=1.0, bid=0.95, ask=1.05), _contract("CALL", symbol="A", midpoint=2.0, bid=1.9, ask=2.1)]

    first = _call_scan(rows)
    second = _call_scan(list(reversed(rows)))

    assert [item.option_contract.option_symbol for item in first] == [item.option_contract.option_symbol for item in second]
    assert [item.ranking_score for item in first] == [item.ranking_score for item in second]
    assert first[0].premium_per_contract == 200.0


def test_covered_call_preferred_dte_ranking():
    rows = [
        _contract("CALL", symbol="D20", dte=20, midpoint=1.333333, bid=1.266666, ask=1.4),
        _contract("CALL", symbol="D30", dte=30, midpoint=2.0, bid=1.9, ask=2.1),
    ]

    assert _call_scan(rows)[0].option_contract.option_symbol == "D30"


def test_covered_call_preferred_delta_ranking():
    rows = [_contract("CALL", symbol="BADDELTA", delta=0.42), _contract("CALL", symbol="GOODDELTA", delta=0.30)]

    assert _call_scan(rows)[0].option_contract.option_symbol == "GOODDELTA"


def test_covered_call_higher_premium_yield_affects_ranking():
    rows = [
        _contract("CALL", symbol="LOWYIELD", midpoint=1.0, bid=0.95, ask=1.05),
        _contract("CALL", symbol="HIGHYIELD", midpoint=2.0, bid=1.9, ask=2.1),
    ]

    assert _call_scan(rows)[0].option_contract.option_symbol == "HIGHYIELD"


def test_covered_call_tighter_spread_affects_ranking():
    rows = [
        _contract("CALL", symbol="WIDE", bid=1.5, ask=2.5, midpoint=2.0),
        _contract("CALL", symbol="TIGHT", bid=1.9, ask=2.1, midpoint=2.0),
    ]

    assert _call_scan(rows)[0].option_contract.option_symbol == "TIGHT"


def test_covered_call_liquidity_affects_ranking():
    rows = [
        _contract("CALL", symbol="LOWLIQ", volume=10, open_interest=50),
        _contract("CALL", symbol="HIGHLIQ", volume=500, open_interest=1000),
    ]

    assert _call_scan(rows)[0].option_contract.option_symbol == "HIGHLIQ"


def test_covered_call_insufficient_shares_rejected():
    [candidate] = _call_scan_all([_contract("CALL")], underlying_quantity=99)

    assert candidate.valid is False
    assert "INSUFFICIENT_UNDERLYING_COVERAGE" in candidate.rejection_reasons


def test_covered_call_wrong_option_type_rejected():
    [candidate] = _call_scan_all([_contract("PUT")])

    assert candidate.valid is False
    assert "OPTION_TYPE_MUST_BE_CALL" in candidate.rejection_reasons


def test_covered_call_excessive_spread_rejected():
    [candidate] = _call_scan_all([_contract("CALL", bid=1.0, ask=3.0, midpoint=2.0)])

    assert candidate.valid is False
    assert "EXCESSIVE_SPREAD" in candidate.rejection_reasons


def test_covered_call_low_volume_rejected():
    [candidate] = _call_scan_all([_contract("CALL", volume=9)])

    assert candidate.valid is False
    assert "LOW_VOLUME" in candidate.rejection_reasons


def test_covered_call_low_open_interest_rejected():
    [candidate] = _call_scan_all([_contract("CALL", open_interest=49)])

    assert candidate.valid is False
    assert "LOW_OPEN_INTEREST" in candidate.rejection_reasons


def test_covered_call_invalid_dte_rejected():
    [candidate] = _call_scan_all([_contract("CALL", dte=3)])

    assert candidate.valid is False
    assert "INVALID_DTE" in candidate.rejection_reasons


def test_covered_call_delta_outside_range_rejected():
    [candidate] = _call_scan_all([_contract("CALL", delta=0.80)])

    assert candidate.valid is False
    assert "DELTA_OUTSIDE_RANGE" in candidate.rejection_reasons


def test_covered_call_missing_prices_rejected():
    [candidate] = _call_scan_all([_contract("CALL", bid=0.0, ask=0.0, midpoint=0.0)])

    assert candidate.valid is False
    assert "MISSING_PRICE_FIELDS" in candidate.rejection_reasons


def test_covered_call_underlying_mismatch_rejected():
    [candidate] = _call_scan_all([_contract("CALL", underlying="QQQ")])

    assert candidate.valid is False
    assert "UNDERLYING_SYMBOL_MISMATCH" in candidate.rejection_reasons


def test_covered_call_malformed_multiplier_rejected():
    [candidate] = _call_scan_all([_bad_row(multiplier=0)])

    assert candidate.valid is False
    assert "MALFORMED_MULTIPLIER" in candidate.rejection_reasons


def test_covered_call_live_mode_rejected():
    [candidate] = _call_scan_all([_contract("CALL")], mode="live")

    assert candidate.valid is False
    assert "UNSUPPORTED_LIVE_MODE" in candidate.rejection_reasons


def test_covered_call_oi002_builder_failure_rejects_candidate(monkeypatch):
    class _Failed:
        valid = False
        rejection_reasons = ("DOMAIN_BLOCKED",)

        def to_dict(self):
            return {"valid": False}

    monkeypatch.setattr(scanner_module, "build_covered_call", lambda **_: _Failed())
    [candidate] = _call_scan_all([_contract("CALL")])

    assert candidate.valid is False
    assert "OI002_BUILDER_REJECTED" in candidate.rejection_reasons
    assert "DOMAIN_BLOCKED" in candidate.rejection_reasons


def test_cash_secured_put_valid_candidate_accepted():
    [candidate] = _put_scan([_contract("PUT")])

    assert candidate.strategy == "CASH_SECURED_PUT"
    assert candidate.valid is True
    assert candidate.strategy_summary["valid"] is True


def test_cash_secured_put_multiple_candidates_ranked_deterministically():
    rows = [_contract("PUT", symbol="PB", midpoint=1.0, bid=0.95, ask=1.05), _contract("PUT", symbol="PA", midpoint=2.0, bid=1.9, ask=2.1)]

    first = _put_scan(rows)
    second = _put_scan(list(reversed(rows)))

    assert [item.option_contract.option_symbol for item in first] == [item.option_contract.option_symbol for item in second]
    assert [item.ranking_score for item in first] == [item.ranking_score for item in second]
    assert first[0].premium_per_contract == 200.0


def test_cash_secured_put_preferred_dte_ranking():
    rows = [
        _contract("PUT", symbol="PD20", dte=20, midpoint=1.333333, bid=1.266666, ask=1.4),
        _contract("PUT", symbol="PD30", dte=30, midpoint=2.0, bid=1.9, ask=2.1),
    ]

    assert _put_scan(rows)[0].option_contract.option_symbol == "PD30"


def test_cash_secured_put_preferred_delta_ranking():
    rows = [_contract("PUT", symbol="PBADDELTA", delta=-0.42), _contract("PUT", symbol="PGOODDELTA", delta=-0.30)]

    assert _put_scan(rows)[0].option_contract.option_symbol == "PGOODDELTA"


def test_cash_secured_put_higher_collateral_efficiency_affects_ranking():
    rows = [
        _contract("PUT", symbol="PLOWEFF", midpoint=1.0, bid=0.95, ask=1.05),
        _contract("PUT", symbol="PHIGHEFF", midpoint=2.0, bid=1.9, ask=2.1),
    ]

    assert _put_scan(rows)[0].option_contract.option_symbol == "PHIGHEFF"


def test_cash_secured_put_tighter_spread_affects_ranking():
    rows = [
        _contract("PUT", symbol="PWIDE", bid=1.5, ask=2.5, midpoint=2.0),
        _contract("PUT", symbol="PTIGHT", bid=1.9, ask=2.1, midpoint=2.0),
    ]

    assert _put_scan(rows)[0].option_contract.option_symbol == "PTIGHT"


def test_cash_secured_put_liquidity_affects_ranking():
    rows = [
        _contract("PUT", symbol="PLOWLIQ", volume=10, open_interest=50),
        _contract("PUT", symbol="PHIGHLIQ", volume=500, open_interest=1000),
    ]

    assert _put_scan(rows)[0].option_contract.option_symbol == "PHIGHLIQ"


def test_cash_secured_put_insufficient_collateral_rejected():
    [candidate] = _put_scan_all([_contract("PUT")], cash_collateral_available=9499.99)

    assert candidate.valid is False
    assert "INSUFFICIENT_CASH_COLLATERAL" in candidate.rejection_reasons


def test_cash_secured_put_missing_collateral_rejected():
    [candidate] = _put_scan_all([_contract("PUT")], cash_collateral_available=None)

    assert candidate.valid is False
    assert "MISSING_COLLATERAL_EVIDENCE" in candidate.rejection_reasons


def test_cash_secured_put_wrong_option_type_rejected():
    [candidate] = _put_scan_all([_contract("CALL")])

    assert candidate.valid is False
    assert "OPTION_TYPE_MUST_BE_PUT" in candidate.rejection_reasons


def test_cash_secured_put_excessive_spread_rejected():
    [candidate] = _put_scan_all([_contract("PUT", bid=1.0, ask=3.0, midpoint=2.0)])

    assert candidate.valid is False
    assert "EXCESSIVE_SPREAD" in candidate.rejection_reasons


def test_cash_secured_put_low_volume_rejected():
    [candidate] = _put_scan_all([_contract("PUT", volume=9)])

    assert candidate.valid is False
    assert "LOW_VOLUME" in candidate.rejection_reasons


def test_cash_secured_put_low_open_interest_rejected():
    [candidate] = _put_scan_all([_contract("PUT", open_interest=49)])

    assert candidate.valid is False
    assert "LOW_OPEN_INTEREST" in candidate.rejection_reasons


def test_cash_secured_put_invalid_dte_rejected():
    [candidate] = _put_scan_all([_contract("PUT", dte=3)])

    assert candidate.valid is False
    assert "INVALID_DTE" in candidate.rejection_reasons


def test_cash_secured_put_delta_outside_range_rejected():
    [candidate] = _put_scan_all([_contract("PUT", delta=-0.80)])

    assert candidate.valid is False
    assert "DELTA_OUTSIDE_RANGE" in candidate.rejection_reasons


def test_cash_secured_put_missing_prices_rejected():
    [candidate] = _put_scan_all([_contract("PUT", bid=0.0, ask=0.0, midpoint=0.0)])

    assert candidate.valid is False
    assert "MISSING_PRICE_FIELDS" in candidate.rejection_reasons


def test_cash_secured_put_underlying_mismatch_rejected():
    [candidate] = _put_scan_all([_contract("PUT", underlying="QQQ")])

    assert candidate.valid is False
    assert "UNDERLYING_SYMBOL_MISMATCH" in candidate.rejection_reasons


def test_cash_secured_put_malformed_multiplier_rejected():
    row = _contract("PUT").to_dict()
    row["multiplier"] = 0
    [candidate] = _put_scan_all([row])

    assert candidate.valid is False
    assert "MALFORMED_MULTIPLIER" in candidate.rejection_reasons


def test_cash_secured_put_live_mode_rejected():
    [candidate] = _put_scan_all([_contract("PUT")], mode="live")

    assert candidate.valid is False
    assert "UNSUPPORTED_LIVE_MODE" in candidate.rejection_reasons


def test_cash_secured_put_oi002_builder_failure_rejects_candidate(monkeypatch):
    class _Failed:
        valid = False
        rejection_reasons = ("DOMAIN_BLOCKED",)

        def to_dict(self):
            return {"valid": False}

    monkeypatch.setattr(scanner_module, "build_cash_secured_put", lambda **_: _Failed())
    [candidate] = _put_scan_all([_contract("PUT")])

    assert candidate.valid is False
    assert "OI002_BUILDER_REJECTED" in candidate.rejection_reasons
    assert "DOMAIN_BLOCKED" in candidate.rejection_reasons


def test_deterministic_ranking_across_repeated_runs():
    rows = [_contract("CALL", symbol="C1", midpoint=2.0, bid=1.9, ask=2.1), _contract("CALL", symbol="C2", midpoint=1.5, bid=1.45, ask=1.55)]
    scanner = IncomeOpportunityScanner()

    first = [item.to_dict() for item in scanner.scan_covered_calls(rows, underlying_symbol="SPY", underlying_price=100, underlying_quantity=100, as_of=AS_OF)]
    second = [item.to_dict() for item in scanner.scan_covered_calls(rows, underlying_symbol="SPY", underlying_price=100, underlying_quantity=100, as_of=AS_OF)]

    assert first == second


def test_stable_tie_breaking():
    rows = [_contract("CALL", symbol="ZZZ"), _contract("CALL", symbol="AAA")]

    result = _call_scan(rows)

    assert [item.option_contract.option_symbol for item in result] == ["AAA", "ZZZ"]


def test_json_safe_summaries():
    [candidate] = _put_scan([_contract("PUT")])

    payload = candidate.to_dict()
    assert json.loads(json.dumps(payload, sort_keys=True))["strategy"] == "CASH_SECURED_PUT"


def test_no_broker_or_execution_calls():
    source = inspect.getsource(scanner_module)

    assert "options_execution_adapter" not in source
    assert "execute_options_order" not in source
    assert "place_order" not in source
    assert "submit_order" not in source


def test_safety_flags_remain_advisory_only():
    candidates = _call_scan([_contract("CALL")]) + _put_scan([_contract("PUT")])

    for candidate in candidates:
        payload = candidate.to_dict()
        assert payload["advisory_only"] is True
        assert payload["execution_allowed"] is False
        assert payload["live_trading_blocked"] is True
        assert payload["broker_execution_armed"] is False


def test_malformed_chain_rows_fail_closed():
    [candidate] = _call_scan_all([{"not": "a contract"}])

    assert candidate.valid is False
    assert "MALFORMED_CHAIN_ROW" in candidate.rejection_reasons


def test_empty_chain_produces_no_candidates():
    assert _call_scan([]) == []
    assert _put_scan([]) == []


def test_original_candidate_rows_are_not_mutated():
    row = _contract("CALL").to_dict()
    original = dict(row)

    _call_scan([row])

    assert row == original


def test_custom_threshold_configuration_is_applied():
    scanner = IncomeOpportunityScanner(IncomeScannerConfig(min_volume=250))
    [candidate] = scanner.scan_covered_calls(
        [_contract("CALL", volume=200)],
        underlying_symbol="SPY",
        underlying_price=100,
        underlying_quantity=100,
        as_of=AS_OF,
        include_rejected=True,
    )

    assert candidate.valid is False
    assert "LOW_VOLUME" in candidate.rejection_reasons
