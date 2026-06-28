from analytics.portfolio_optimizer import (
    PortfolioAllocationPlan,
    StrategyAllocation,
)


def test_empty_plan_totals():
    plan = PortfolioAllocationPlan(
        generated_at="2026-06-28T15:00:00Z",
        market_regime="TRENDING",
        risk_profile="BALANCED",
        total_capital=10000.0,
    )

    assert plan.total_allocated_percent() == 0.0
    assert plan.total_allocated_amount() == 0.0
    assert plan.validation_status == "PENDING"


def test_plan_totals():
    plan = PortfolioAllocationPlan(
        generated_at="2026-06-28T15:00:00Z",
        market_regime="TRENDING",
        risk_profile="BALANCED",
        total_capital=10000.0,
    )

    plan.allocations.append(
        StrategyAllocation(
            strategy_id="trend_following",
            allocation_percent=60.0,
            allocation_amount=6000.0,
            confidence=0.93,
            expected_risk=0.11,
            rationale="Highest institutional score",
        )
    )

    plan.allocations.append(
        StrategyAllocation(
            strategy_id="mean_reversion",
            allocation_percent=40.0,
            allocation_amount=4000.0,
            confidence=0.87,
            expected_risk=0.08,
            rationale="Portfolio diversification",
        )
    )

    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 10000.0


def test_plan_dictionary_export():
    plan = PortfolioAllocationPlan(
        generated_at="2026-06-28T15:00:00Z",
        market_regime="RANGE",
        risk_profile="CONSERVATIVE",
        total_capital=5000.0,
    )

    plan.allocations.append(
        StrategyAllocation(
            strategy_id="carry_trade",
            allocation_percent=100.0,
            allocation_amount=5000.0,
            confidence=0.90,
            expected_risk=0.05,
            rationale="Example",
        )
    )

    exported = plan.to_dict()

    assert exported["risk_profile"] == "CONSERVATIVE"
    assert exported["market_regime"] == "RANGE"
    assert exported["validation_status"] == "PENDING"
    assert exported["total_allocated_percent"] == 100.0
    assert exported["total_allocated_amount"] == 5000.0
    assert len(exported["allocations"]) == 1
