from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.allocation import OpportunityProposal
from backend.allocation.caie_portfolio_optimizer import CAIEPortfolioOptimizer


NOW = datetime(2026, 9, 14, 23, 55, tzinfo=timezone.utc)


def proposal(
    proposal_id,
    *,
    broker="PAPER",
    asset_class="EQUITY",
    symbol="AAPL",
    capital="500",
    pwin="0.80",
    eret="0.10",
    drawdown="0.03",
):
    return OpportunityProposal(
        proposal_id=proposal_id,
        source="optimizer-test",
        broker=broker,
        symbol=symbol,
        asset_class=asset_class,
        side="BUY",
        probability_win=Decimal(pwin),
        confidence=Decimal("0.80"),
        capital_required=Decimal(capital),
        max_drawdown_pct=Decimal(drawdown),
        expected_return_pct=Decimal(eret),
        liquidity_score=Decimal("0.95"),
        regime_alignment=Decimal("0.95"),
        observed_at_utc=NOW,
    )


def test_optimizer_never_exceeds_available_capital():
    plan = CAIEPortfolioOptimizer.optimize(
        [proposal("a", capital="800"), proposal("b", symbol="MSFT", capital="800")],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("1")},
        broker_caps={"PAPER": Decimal("1")},
        concentration_cap=Decimal("1"),
    )
    assert plan.deployed_capital <= Decimal("1000")
    assert plan.remaining_cash >= 0


def test_optimizer_respects_asset_class_caps():
    plan = CAIEPortfolioOptimizer.optimize(
        [
            proposal("eq", asset_class="EQUITY", capital="900"),
            proposal("fx", asset_class="FX", broker="OANDA", symbol="EUR_USD", capital="900"),
        ],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("0.30"), "FX": Decimal("0.40")},
        broker_caps={"PAPER": Decimal("1"), "OANDA": Decimal("1")},
        concentration_cap=Decimal("1"),
    )
    by_asset = {item.asset_class: item.allocated_capital for item in plan.allocations}
    assert by_asset["EQUITY"] <= Decimal("300")
    assert by_asset["FX"] <= Decimal("400")


def test_optimizer_respects_broker_caps():
    plan = CAIEPortfolioOptimizer.optimize(
        [
            proposal("a", broker="BROKER_A", capital="700"),
            proposal("b", broker="BROKER_A", symbol="MSFT", capital="700"),
        ],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("1")},
        broker_caps={"BROKER_A": Decimal("0.40")},
        concentration_cap=Decimal("1"),
    )
    assert sum(x.allocated_capital for x in plan.allocations) <= Decimal("400")


def test_optimizer_limits_single_opportunity_concentration():
    plan = CAIEPortfolioOptimizer.optimize(
        [proposal("big", capital="900")],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("1")},
        broker_caps={"PAPER": Decimal("1")},
        concentration_cap=Decimal("0.25"),
    )
    assert plan.allocations[0].allocated_capital == Decimal("250")
    assert plan.allocations[0].concentration_limited is True


def test_optimizer_can_hold_cash_when_opportunities_unattractive():
    bad = proposal(
        "bad",
        pwin="0.10",
        eret="0.01",
        drawdown="0.20",
        capital="500",
    )
    plan = CAIEPortfolioOptimizer.optimize(
        [bad],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("1")},
        broker_caps={"PAPER": Decimal("1")},
    )
    assert plan.allocations == ()
    assert plan.deployed_capital == 0
    assert plan.remaining_cash == Decimal("1000")


def test_higher_scored_opportunity_is_ranked_first():
    strong = proposal("strong", symbol="AAPL", pwin="0.90", eret="0.12")
    weaker = proposal("weaker", symbol="MSFT", pwin="0.65", eret="0.08")
    plan = CAIEPortfolioOptimizer.optimize(
        [weaker, strong],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("1")},
        broker_caps={"PAPER": Decimal("1")},
        concentration_cap=Decimal("0.50"),
    )
    assert plan.allocations[0].proposal_id == "strong"


def test_unknown_cap_defaults_to_zero_and_fails_safe():
    plan = CAIEPortfolioOptimizer.optimize(
        [proposal("unknown", asset_class="OPTIONS", broker="PAPER")],
        available_capital=Decimal("1000"),
        asset_class_caps={},
        broker_caps={"PAPER": Decimal("1")},
    )
    assert plan.allocations == ()
    assert plan.remaining_cash == Decimal("1000")


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("1.01")])
def test_invalid_concentration_cap_fails_closed(value):
    with pytest.raises(ValueError):
        CAIEPortfolioOptimizer.optimize(
            [],
            available_capital=Decimal("1000"),
            asset_class_caps={},
            broker_caps={},
            concentration_cap=value,
        )


def test_plan_remains_shadow_only():
    plan = CAIEPortfolioOptimizer.optimize(
        [proposal("a")],
        available_capital=Decimal("1000"),
        asset_class_caps={"EQUITY": Decimal("1")},
        broker_caps={"PAPER": Decimal("1")},
    )
    assert plan.status == "SHADOW_ONLY"
    assert not hasattr(CAIEPortfolioOptimizer, "place_order")
