from __future__ import annotations

import inspect
import json
from datetime import date, timedelta

import pytest

import backend.options.options_income_portfolio as portfolio_module
from backend.options.options_income_allocator import OptionsIncomeAllocator
from backend.options.options_income_constraints import (
    OptionsIncomeConstraintConfig,
    OptionsIncomeConstraintEngine,
    OptionsIncomeConstraintError,
)
from backend.options.options_income_laddering import OptionsIncomeLadderBuilder, OptionsIncomeLadderingError
from backend.options.options_income_opportunity_scanner import IncomeOpportunityScanner
from backend.options.options_income_portfolio import OptionsIncomePortfolioConstructor, OptionsIncomePortfolioError
from backend.options.options_income_rebalancer import OptionsIncomeRebalancer
from backend.options.options_income_targets import OptionsIncomeTargetCalculator
from backend.options.paper_income_lifecycle import PaperIncomeLifecycleEngine
from backend.options.paper_position_repository import PaperIncomePosition, PaperPositionRepository, PaperPositionRepositoryError
from backend.trading.option_contract import CanonicalOptionContract


AS_OF = date(2026, 7, 14)
ENTRY_DATE = AS_OF.isoformat()
EXPIRY_1 = (AS_OF + timedelta(days=30)).isoformat()
EXPIRY_2 = (AS_OF + timedelta(days=37)).isoformat()
EXPIRY_3 = (AS_OF + timedelta(days=17)).isoformat()
NOW = "2026-07-14T00:00:00+00:00"


def _clock() -> str:
    return NOW


def _contract(
    option_type: str,
    *,
    underlying: str,
    expiry: str,
    strike: float | None = None,
    symbol: str | None = None,
) -> CanonicalOptionContract:
    option_type = option_type.upper()
    strike = 105.0 if strike is None and option_type == "CALL" else (95.0 if strike is None else strike)
    return CanonicalOptionContract.from_dict(
        {
            "underlying_symbol": underlying,
            "option_symbol": symbol or f"{underlying}-{expiry}-{option_type[0]}-{int(strike)}",
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


def _active_position(candidate=None) -> PaperIncomePosition:
    repository = PaperPositionRepository()
    engine = PaperIncomeLifecycleEngine(repository=repository, clock=_clock)
    position = engine.create_position(candidate or _call_candidate("AAPL", EXPIRY_3), entry_date=ENTRY_DATE)
    engine.approve_position(position.position_id)
    engine.open_position(position.position_id)
    return engine.activate_position(position.position_id)


def _portfolio(opportunities=None, positions=None, capital=60000):
    return OptionsIncomePortfolioConstructor().construct(
        portfolio_id="OI006-PAPER",
        total_capital=capital,
        opportunities=opportunities if opportunities is not None else [_call_candidate(), _put_candidate(), _call_candidate("AAPL", EXPIRY_3)],
        existing_positions=positions or [],
        sector_by_underlying={"SPY": "ETF", "QQQ": "ETF", "AAPL": "TECH"},
        annual_target_yield=0.10,
    )


def test_portfolio_construction_from_oi003_opportunities():
    portfolio = _portfolio()
    payload = portfolio.to_dict()

    assert payload["portfolio_id"] == "OI006-PAPER"
    assert len(payload["allocations"]) == 3
    assert payload["capital"]["allocated_capital"] > 0
    assert payload["execution_allowed"] is False
    assert payload["rebalance"]["action"] in {"Maintain Portfolio", "Increase Allocation", "Reduce Allocation", "Roll Portfolio", "Replace Opportunity"}


def test_capital_allocation_tracks_available_reserved_and_unused():
    existing = _active_position(_call_candidate("AAPL", EXPIRY_3))
    portfolio = _portfolio(positions=[existing])
    capital = portfolio.to_dict()["capital"]

    assert capital["reserved_collateral"] == 100.0
    assert capital["utilized_collateral"] >= capital["reserved_collateral"]
    assert capital["available_capital"] + capital["allocated_capital"] == 60000.0
    assert 0.0 < capital["portfolio_utilization"] < 1.0


def test_diversification_reports_underlying_strategy_sector_and_assignment():
    payload = _portfolio().to_dict()
    report = payload["diversification"]

    assert set(report["by_underlying"]) == {"AAPL", "QQQ", "SPY"}
    assert "COVERED_CALL" in report["by_strategy"]
    assert "CASH_SECURED_PUT" in report["by_strategy"]
    assert "ETF" in report["by_sector"]
    assert report["assignment_concentration"]["SPY"] > 0
    assert 0.0 <= report["diversification_score"] <= 100.0


def test_expiry_laddering_supports_mixed_distribution():
    ladder = _portfolio().to_dict()["ladder"]

    assert ladder["ladder_type"] == "MIXED"
    assert ladder["mixed_ladder"] is True
    assert len(ladder["expiry_distribution"]) == 3
    assert ladder["ladder_quality_score"] > 0


def test_income_targets_calculate_expected_premium_and_yield():
    targets = _portfolio().to_dict()["income_targets"]

    assert targets["monthly_premium_target"] == 500.0
    assert targets["annual_premium_target"] == 6000.0
    assert targets["expected_premium"] == 600.0
    assert targets["portfolio_yield"] > 0
    assert targets["yield_on_collateral"] > 0
    assert targets["capital_efficiency"] > 0


def test_rebalancer_recommends_increase_when_underallocated():
    recommendation = OptionsIncomeRebalancer().recommend(
        allocation={"portfolio_utilization": 0.10, "blockers": []},
        diversification={"diversification_score": 90.0},
        ladder={"ladder_quality_score": 90.0},
        targets={"expected_premium": 100.0, "monthly_premium_target": 500.0},
    )

    assert recommendation.action == "Increase Allocation"
    assert recommendation.execution_allowed is False


def test_rebalancer_recommends_replace_when_blocked():
    recommendation = OptionsIncomeRebalancer().recommend(
        allocation={"portfolio_utilization": 0.40, "blockers": ["single underlying concentration violation"]},
        diversification={"diversification_score": 90.0},
        ladder={"ladder_quality_score": 90.0},
        targets={"expected_premium": 500.0, "monthly_premium_target": 500.0},
    )

    assert recommendation.action == "Replace Opportunity"


def test_constraint_rejects_negative_capital():
    with pytest.raises(OptionsIncomeConstraintError):
        OptionsIncomeConstraintEngine().validate_capital(-1)


def test_constraint_rejects_single_underlying_concentration():
    engine = OptionsIncomeConstraintEngine(OptionsIncomeConstraintConfig(max_single_underlying_pct=0.10))
    allocator = OptionsIncomeAllocator(engine)

    plan = allocator.allocate(total_capital=60000, opportunities=[_call_candidate("SPY", EXPIRY_1)], sector_by_underlying={"SPY": "ETF"})

    assert plan.allocations == []
    assert any("single underlying concentration violation" in blocker for blocker in plan.blockers)


def test_constraint_rejects_duplicate_allocation_identifiers():
    row = {
        "allocation_id": "DUP",
        "strategy": "COVERED_CALL",
        "underlying": "SPY",
        "expiry": EXPIRY_1,
        "collateral": 1000,
        "assignment_exposure": 1000,
    }

    with pytest.raises(OptionsIncomeConstraintError):
        OptionsIncomeConstraintEngine().validate_allocations([row, dict(row)], total_capital=10000)


def test_allocator_records_blockers_for_duplicate_opportunity():
    candidate = _call_candidate("SPY", EXPIRY_1)
    plan = OptionsIncomeAllocator().allocate(
        total_capital=60000,
        opportunities=[candidate, candidate],
        sector_by_underlying={"SPY": "ETF"},
    )

    assert len(plan.allocations) == 1
    assert any("Duplicate opportunity" in blocker for blocker in plan.blockers)


def test_invalid_ladder_fails_closed():
    with pytest.raises(OptionsIncomeLadderingError):
        OptionsIncomeLadderBuilder().build([{"expiry": "not-a-date", "collateral": 1000}])


def test_invalid_portfolio_id_fails_closed():
    with pytest.raises(OptionsIncomePortfolioError):
        OptionsIncomePortfolioConstructor().construct(portfolio_id="", total_capital=10000)


def test_unsupported_strategy_fails_closed():
    payload = _call_candidate().to_dict()
    payload["strategy"] = "IRON_CONDOR"

    plan = OptionsIncomeAllocator().allocate(total_capital=60000, opportunities=[payload])

    assert plan.allocations == []
    assert any("Unsupported strategy" in blocker for blocker in plan.blockers)


def test_invalid_collateral_fails_closed():
    payload = _call_candidate().to_dict()
    payload["collateral_required"] = -1

    plan = OptionsIncomeAllocator().allocate(total_capital=60000, opportunities=[payload])

    assert plan.allocations == []
    assert any("collateral_required" in blocker for blocker in plan.blockers)


def test_repository_corruption_fails_closed(tmp_path):
    path = tmp_path / "paper_positions.json"
    path.write_text("{bad-json", encoding="utf-8")

    with pytest.raises(PaperPositionRepositoryError):
        PaperPositionRepository(path)


def test_oi005_oi004_oi003_oi002_integration():
    candidate = _call_candidate("AAPL", EXPIRY_3)
    existing = _active_position(candidate)
    portfolio = _portfolio(opportunities=[_call_candidate(), _put_candidate()], positions=[existing])
    payload = portfolio.to_dict()

    assert candidate.strategy_summary["valid"] is True
    assert existing.current_state == "ACTIVE"
    assert any(row["source"] == "OI-004_POSITION" for row in payload["allocations"])
    assert any(row["source"] == "OI-003_OPPORTUNITY" for row in payload["allocations"])


def test_portfolio_payload_is_idempotent_and_json_serializable():
    first = _portfolio().to_dict()
    second = _portfolio().to_dict()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True))["advisory_only"] is True


def test_income_target_rejects_negative_capital():
    with pytest.raises(ValueError):
        OptionsIncomeTargetCalculator().calculate([], total_capital=-100)


def test_fail_closed_invalid_existing_position_strategy():
    existing = _active_position(_call_candidate("AAPL", EXPIRY_3))
    bad = PaperIncomePosition.from_dict({**existing.to_dict(), "strategy_type": "BAD"})

    with pytest.raises(OptionsIncomeConstraintError):
        _portfolio(positions=[bad])


def test_no_broker_or_execution_calls_in_oi006_portfolio_module():
    source = inspect.getsource(portfolio_module)

    assert "submit_order" not in source
    assert "place_order" not in source
    assert "execute_trade" not in source
    assert "enable_live" not in source
