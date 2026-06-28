from analytics.portfolio_optimizer_engine import PortfolioOptimizerEngine


def test_balanced_profile_remains_equal_weight():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_risk_profile_plan(
        ["A", "B", "C"],
        total_capital=900.0,
        risk_profile="BALANCED",
    )

    assert plan.total_allocated_percent() == 100.0
    assert [a.allocation_percent for a in plan.allocations] == [33.3333, 33.3333, 33.3334]


def test_growth_profile_favors_first_strategy():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_risk_profile_plan(
        ["A", "B", "C"],
        total_capital=900.0,
        risk_profile="GROWTH",
    )

    assert plan.allocations[0].allocation_percent > plan.allocations[1].allocation_percent
    assert plan.allocations[1].allocation_percent > plan.allocations[2].allocation_percent
    assert plan.total_allocated_percent() == 100.0


def test_opportunistic_profile_preserves_totals():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_risk_profile_plan(
        ["A", "B", "C", "D"],
        total_capital=1000.0,
        risk_profile="OPPORTUNISTIC",
    )

    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 1000.0
    assert plan.diversification_metrics["strategy_count"] == 4
