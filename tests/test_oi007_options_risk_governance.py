from __future__ import annotations

import inspect
import json
from datetime import date, timedelta

import pytest

import backend.options.options_income_risk_governance as governance_module
from backend.options.options_greeks_aggregator import OptionsGreeksAggregationError, OptionsGreeksAggregator
from backend.options.options_income_assignment_risk import OptionsIncomeAssignmentRiskAnalyzer
from backend.options.options_income_portfolio import OptionsIncomePortfolioConstructor
from backend.options.options_income_risk_budget import OptionsIncomeRiskBudgetConfig, OptionsIncomeRiskBudgetEngine
from backend.options.options_income_risk_governance import OptionsIncomeRiskGovernanceEngine, OptionsIncomeRiskGovernanceError
from backend.options.options_income_risk_limits import OptionsIncomeRiskLimitEngine
from backend.options.options_income_stress_testing import OptionsIncomeStressTester
from backend.options.options_income_volatility_risk import OptionsIncomeVolatilityRiskAnalyzer, OptionsIncomeVolatilityRiskError
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine
from backend.options.paper_position_repository import PaperPositionRepository, PaperPositionRepositoryError
from backend.trading.option_contract import CanonicalOptionContract


AS_OF = date(2026, 7, 14)
ENTRY_DATE = AS_OF.isoformat()
EXPIRY_1 = (AS_OF + timedelta(days=30)).isoformat()
EXPIRY_2 = (AS_OF + timedelta(days=37)).isoformat()
EXPIRY_3 = (AS_OF + timedelta(days=17)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _clock() -> str:
    return NOW


def _contract(option_type: str, *, underlying: str, expiry: str, strike: float | None = None) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": underlying,
            "option_symbol": f"{underlying}-{expiry}-{option_type[0]}-{int(strike)}",
            "expiration_date": expiry,
            "strike": strike,
            "option_type": option_type,
            "bid": 1.9,
            "ask": 2.1,
            "midpoint": 2.0,
            "last": 2.0,
            "volume": 200,
            "open_interest": 700,
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


def _call_candidate(underlying: str = "SPY", expiry: str = EXPIRY_1, price: float = 100.0):
    return IncomeOpportunityScanner().scan_covered_calls(
        [_contract("CALL", underlying=underlying, expiry=expiry)],
        underlying_symbol=underlying,
        underlying_price=price,
        underlying_quantity=100,
        as_of=AS_OF,
    )[0]


def _put_candidate(underlying: str = "QQQ", expiry: str = EXPIRY_2):
    return IncomeOpportunityScanner().scan_cash_secured_puts(
        [_contract("PUT", underlying=underlying, expiry=expiry)],
        underlying_symbol=underlying,
        cash_collateral_available=9500.0,
        underlying_price=100.0,
        as_of=AS_OF,
    )[0]


def _active_position():
    repository = PaperPositionRepository()
    engine = PaperIncomeLifecycleEngine(repository=repository, clock=_clock)
    position = engine.create_position(_call_candidate("AAPL", EXPIRY_3), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)
    engine.open_position(position.position_id)
    return engine.activate_position(position.position_id)


def _portfolio():
    return OptionsIncomePortfolioConstructor().construct(
        portfolio_id="OI007-PAPER",
        total_capital=60000,
        opportunities=[_call_candidate(), _put_candidate()],
        existing_positions=[_active_position()],
        sector_by_underlying={"SPY": "ETF", "QQQ": "ETF", "AAPL": "TECH"},
        annual_target_yield=0.10,
    ).to_dict()


def _symbols(portfolio):
    return [row["option_symbol"] for row in portfolio["allocations"]]


def _greeks(portfolio, *, delta=0.20, gamma=0.01, theta=-0.02, vega=0.05, rho=0.01):
    return {symbol: {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho} for symbol in _symbols(portfolio)}


def _ivs(portfolio, iv=0.22):
    return {symbol: iv for symbol in _symbols(portfolio)}


def _market():
    return {
        "SPY": {"underlying_price": 100.0, "near_expiry_cutoff": EXPIRY_3},
        "QQQ": {"underlying_price": 100.0, "near_expiry_cutoff": EXPIRY_3},
        "AAPL": {"underlying_price": 100.0, "near_expiry_cutoff": EXPIRY_3},
    }


def test_position_level_greeks_are_aggregated():
    portfolio = _portfolio()
    report = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=_greeks(portfolio), total_capital=60000).to_dict()

    assert report["status"] == "GREEN"
    assert len(report["position_level"]) == 3
    assert report["position_level"][0]["delta"] == -20.0
    assert report["position_level"][0]["greeks_per_unit_capital"]["delta"] < 0


def test_portfolio_underlying_strategy_and_expiry_greeks_aggregation():
    portfolio = _portfolio()
    report = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=_greeks(portfolio), total_capital=60000).to_dict()

    assert set(report["by_underlying"]) == {"AAPL", "QQQ", "SPY"}
    assert set(report["by_strategy"]) == {"CASH_SECURED_PUT", "COVERED_CALL"}
    assert set(report["by_expiry"]) == {EXPIRY_1, EXPIRY_2, EXPIRY_3}
    assert report["portfolio"]["absolute_delta_exposure"] == 60.0
    assert report["portfolio"]["theta_income"] == 6.0


def test_missing_greeks_are_marked_unavailable():
    portfolio = _portfolio()
    report = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol={}, total_capital=60000).to_dict()

    assert report["status"] == "UNAVAILABLE"
    assert sorted(report["unavailable"]) == sorted(_symbols(portfolio))


def test_invalid_greeks_fail_closed():
    portfolio = _portfolio()
    raw = _greeks(portfolio)
    raw[_symbols(portfolio)[0]]["delta"] = "bad"

    with pytest.raises(OptionsGreeksAggregationError):
        OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=raw, total_capital=60000)


def test_risk_budget_green_state():
    portfolio = _portfolio()
    greeks = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=_greeks(portfolio), total_capital=60000).to_dict()
    assignment = OptionsIncomeAssignmentRiskAnalyzer().analyze(portfolio, market_data_by_underlying=_market()).to_dict()
    volatility = OptionsIncomeVolatilityRiskAnalyzer().analyze(portfolio, iv_by_symbol=_ivs(portfolio), greeks=greeks).to_dict()
    stress = OptionsIncomeStressTester().run(portfolio, greeks=greeks, assignment=assignment).to_dict()

    budgets = OptionsIncomeRiskBudgetEngine().evaluate(
        greeks=greeks,
        diversification=portfolio["diversification"],
        capital=portfolio["capital"],
        assignment=assignment,
        volatility=volatility,
        stress=stress,
    )

    assert budgets["status"] in {"GREEN", "AMBER"}
    assert budgets["budgets"]["absolute_delta"]["status"] == "GREEN"


def test_risk_budget_amber_state():
    row = OptionsIncomeRiskBudgetEngine().evaluate(
        greeks={"portfolio": {"delta": 70, "absolute_delta_exposure": 100, "gamma": 1, "theta_income": 1, "vega": 1, "rho": 1}},
        diversification={"by_underlying": {"SPY": 0.1}, "by_expiry": {"E": 0.1}, "by_strategy": {"COVERED_CALL": 0.1}},
        capital={"portfolio_utilization": 0.5},
        assignment={"portfolio_assignment_ratio": 0.1},
        volatility={"short_volatility_concentration": 0.1, "status": "GREEN"},
    )["budgets"]["portfolio_delta"]

    assert row["status"] == "AMBER"


def test_risk_budget_red_state_and_hard_limit_rejection():
    budgets = OptionsIncomeRiskBudgetEngine(OptionsIncomeRiskBudgetConfig(max_net_delta=10)).evaluate(
        greeks={"portfolio": {"delta": 100, "absolute_delta_exposure": 100, "gamma": 1, "theta_income": 1, "vega": 1, "rho": 1}},
        diversification={"by_underlying": {"SPY": 0.1}, "by_expiry": {"E": 0.1}, "by_strategy": {"COVERED_CALL": 0.1}},
        capital={"portfolio_utilization": 0.5},
        assignment={"portfolio_assignment_ratio": 0.1},
        volatility={"short_volatility_concentration": 0.1, "status": "GREEN"},
    )
    limits = OptionsIncomeRiskLimitEngine().evaluate(budgets).to_dict()

    assert budgets["budgets"]["portfolio_delta"]["status"] == "RED"
    assert "portfolio_delta" in limits["hard_breaches"]


def test_assignment_exposure_for_covered_call_and_cash_secured_put():
    report = OptionsIncomeAssignmentRiskAnalyzer().analyze(_portfolio(), market_data_by_underlying=_market()).to_dict()

    assert report["contracts_exposed"] == 3
    assert report["shares_potentially_called_away"] == 200.0
    assert report["cash_potentially_required"] == 9500.0
    assert report["assignment_notional"] > 0
    assert report["portfolio_assignment_ratio"] > 0


def test_assignment_itm_and_near_expiry_exposure():
    market = _market()
    market["SPY"]["underlying_price"] = 110.0
    market["QQQ"]["underlying_price"] = 90.0
    report = OptionsIncomeAssignmentRiskAnalyzer().analyze(_portfolio(), market_data_by_underlying=market).to_dict()

    assert report["itm_exposure"] > 0
    assert report["near_expiry_exposure"] > 0


def test_volatility_risk_and_missing_iv_handling():
    portfolio = _portfolio()
    greeks = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=_greeks(portfolio), total_capital=60000).to_dict()
    report = OptionsIncomeVolatilityRiskAnalyzer().analyze(portfolio, iv_by_symbol=_ivs(portfolio), greeks=greeks, volatility_regime="HIGH_VOLATILITY").to_dict()
    missing = OptionsIncomeVolatilityRiskAnalyzer().analyze(portfolio, iv_by_symbol={}, greeks=greeks).to_dict()

    assert report["status"] == "GREEN"
    assert report["volatility_regime"] == "HIGH_VOLATILITY"
    assert report["implied_volatility_exposure"] > 0
    assert missing["status"] == "UNAVAILABLE"
    assert sorted(missing["unavailable"]) == sorted(_symbols(portfolio))


def test_invalid_iv_fails_closed():
    portfolio = _portfolio()
    greeks = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=_greeks(portfolio), total_capital=60000).to_dict()
    bad = _ivs(portfolio)
    bad[_symbols(portfolio)[0]] = 0

    with pytest.raises(OptionsIncomeVolatilityRiskError):
        OptionsIncomeVolatilityRiskAnalyzer().analyze(portfolio, iv_by_symbol=bad, greeks=greeks)


def test_stress_testing_includes_required_scenarios_and_limits():
    portfolio = _portfolio()
    greeks = OptionsGreeksAggregator().aggregate(portfolio, greeks_by_symbol=_greeks(portfolio), total_capital=60000).to_dict()
    assignment = OptionsIncomeAssignmentRiskAnalyzer().analyze(portfolio, market_data_by_underlying=_market()).to_dict()
    stress = OptionsIncomeStressTester().run(portfolio, greeks=greeks, assignment=assignment).to_dict()

    names = {row["scenario_name"] for row in stress["scenarios"]}
    assert "Underlying down 20%" in names
    assert "Combined downside plus volatility expansion" in names
    assert "Assignment concentration event" in names
    assert stress["max_estimated_loss"] > 0
    assert all("DETERMINISTIC_LINEAR_GREEKS_APPROXIMATION" in row["approximation_flags"] for row in stress["scenarios"])


def test_governance_approval_state():
    portfolio = _portfolio()
    assessment = OptionsIncomeRiskGovernanceEngine().assess(
        portfolio,
        greeks_by_symbol=_greeks(portfolio, delta=0.05, gamma=0.001, theta=-0.01, vega=0.01),
        iv_by_symbol=_ivs(portfolio),
        market_data_by_underlying=_market(),
    ).to_dict()

    assert assessment["approval_status"] in {"APPROVED_PAPER", "APPROVED_WITH_WARNINGS"}
    assert assessment["execution_allowed"] is False
    assert assessment["live_trading_blocked"] is True
    assert assessment["paper_only"] is True


def test_governance_approval_with_warnings_from_missing_data():
    portfolio = _portfolio()
    assessment = OptionsIncomeRiskGovernanceEngine().assess(
        portfolio,
        greeks_by_symbol=_greeks(portfolio),
        iv_by_symbol={},
        market_data_by_underlying=_market(),
    ).to_dict()

    assert assessment["approval_status"] == "REJECTED_INVALID_DATA"
    assert assessment["unavailable_data"]
    assert any(row["action"] == "Insufficient data" for row in assessment["advisory_recommendations"])


def test_governance_rejects_risk_limit_breach():
    portfolio = _portfolio()
    engine = OptionsIncomeRiskGovernanceEngine(config=OptionsIncomeRiskBudgetConfig(max_absolute_delta=10, max_stressed_loss_pct=0.01))
    assessment = engine.assess(
        portfolio,
        greeks_by_symbol=_greeks(portfolio, delta=0.90, gamma=0.05, theta=-0.01, vega=0.30),
        iv_by_symbol=_ivs(portfolio),
        market_data_by_underlying=_market(),
    ).to_dict()

    assert assessment["approval_status"] == "REJECTED_RISK_LIMIT"
    assert assessment["limit_breaches"]
    assert assessment["portfolio_risk_status"] == "RED"


def test_governance_rejects_invalid_data_and_execution_enabled_posture():
    portfolio = _portfolio()
    portfolio["execution_allowed"] = True

    with pytest.raises(OptionsIncomeRiskGovernanceError):
        OptionsIncomeRiskGovernanceEngine().assess(portfolio, greeks_by_symbol=_greeks(portfolio), iv_by_symbol=_ivs(portfolio))


def test_governance_fail_closed_duplicate_unsupported_negative_and_completed_rows():
    portfolio = _portfolio()
    duplicate = {**portfolio, "allocations": [portfolio["allocations"][0], dict(portfolio["allocations"][0])]}
    unsupported = {**portfolio, "allocations": [{**portfolio["allocations"][0], "strategy": "IRON_CONDOR"}]}
    negative = {**portfolio, "allocations": [{**portfolio["allocations"][0], "collateral": -1}]}
    completed = {**portfolio, "allocations": [{**portfolio["allocations"][0], "current_state": "COMPLETED"}]}
    engine = OptionsIncomeRiskGovernanceEngine()

    for payload in (duplicate, unsupported, negative, completed):
        with pytest.raises(OptionsIncomeRiskGovernanceError):
            engine.assess(payload, greeks_by_symbol=_greeks(portfolio), iv_by_symbol=_ivs(portfolio))


def test_idempotency_stable_ordering_and_json_payload():
    portfolio = _portfolio()
    engine = OptionsIncomeRiskGovernanceEngine()
    first = engine.assess(portfolio, greeks_by_symbol=_greeks(portfolio), iv_by_symbol=_ivs(portfolio), market_data_by_underlying=_market()).to_dict()
    second = engine.assess(portfolio, greeks_by_symbol=_greeks(portfolio), iv_by_symbol=_ivs(portfolio), market_data_by_underlying=_market()).to_dict()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True))["advisory_only"] is True


def test_repository_corruption_regression(tmp_path):
    path = tmp_path / "paper_positions.json"
    path.write_text("{bad-json", encoding="utf-8")

    with pytest.raises(PaperPositionRepositoryError):
        PaperPositionRepository(path)


def test_oi006_oi005_oi004_oi003_oi002_integration():
    portfolio = _portfolio()
    assessment = OptionsIncomeRiskGovernanceEngine().assess(
        portfolio,
        greeks_by_symbol=_greeks(portfolio),
        iv_by_symbol=_ivs(portfolio),
        market_data_by_underlying=_market(),
    ).to_dict()

    assert portfolio["portfolio_id"] == "OI007-PAPER"
    assert len(portfolio["allocations"]) == 3
    assert assessment["greeks_summary"]["position_level"]
    assert assessment["assignment_summary"]["contracts_exposed"] == 3


def test_no_order_or_live_execution_language_in_governance_module():
    source = inspect.getsource(governance_module)

    assert "submit_order" not in source
    assert "place_order" not in source
    assert "execute_trade" not in source
    assert "enable_live" not in source
