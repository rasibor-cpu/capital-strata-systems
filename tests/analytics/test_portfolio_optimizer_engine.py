from analytics.portfolio_optimizer_engine import PortfolioOptimizerEngine


def test_empty_strategy_list():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_equal_weight_plan([], total_capital=1000.0)

    assert plan.total_allocated_percent() == 0.0
    assert plan.total_allocated_amount() == 0.0
    assert len(plan.allocations) == 0


def test_single_strategy():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_equal_weight_plan(["trend"], total_capital=1000.0)

    assert len(plan.allocations) == 1
    assert plan.allocations[0].allocation_percent == 100.0
    assert plan.allocations[0].allocation_amount == 1000.0


def test_three_strategies_sum_to_100():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_equal_weight_plan(
        ["trend", "momentum", "mean_reversion"],
        total_capital=900.0,
    )

    assert len(plan.allocations) == 3
    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 900.0
