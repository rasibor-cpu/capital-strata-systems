from analytics.portfolio_optimizer_engine import PortfolioOptimizerEngine


def test_trending_regime_favors_trend_and_momentum():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_market_regime_plan(
        ["trend_following", "mean_reversion", "momentum_breakout"],
        total_capital=900.0,
        market_regime="TRENDING",
        risk_profile="BALANCED",
    )

    allocations = {item.strategy_id: item.allocation_percent for item in plan.allocations}

    assert allocations["trend_following"] > allocations["mean_reversion"]
    assert allocations["momentum_breakout"] > allocations["mean_reversion"]
    assert plan.total_allocated_percent() == 100.0


def test_range_regime_favors_mean_reversion():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_market_regime_plan(
        ["trend_following", "mean_reversion", "momentum"],
        total_capital=900.0,
        market_regime="RANGE",
        risk_profile="BALANCED",
    )

    allocations = {item.strategy_id: item.allocation_percent for item in plan.allocations}

    assert allocations["mean_reversion"] > allocations["trend_following"]
    assert allocations["mean_reversion"] > allocations["momentum"]
    assert plan.total_allocated_percent() == 100.0


def test_volatile_regime_preserves_totals():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_market_regime_plan(
        ["trend_following", "defensive_hedge", "mean_reversion"],
        total_capital=1200.0,
        market_regime="VOLATILE",
        risk_profile="BALANCED",
    )

    allocations = {item.strategy_id: item.allocation_percent for item in plan.allocations}

    assert allocations["defensive_hedge"] > allocations["trend_following"]
    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 1200.0


def test_unknown_regime_falls_back_to_equal_weight():
    engine = PortfolioOptimizerEngine()
    plan = engine.build_market_regime_plan(
        ["A", "B", "C"],
        total_capital=900.0,
        market_regime="UNKNOWN",
        risk_profile="BALANCED",
    )

    assert [item.allocation_percent for item in plan.allocations] == [
        33.3333,
        33.3333,
        33.3334,
    ]
    assert plan.total_allocated_percent() == 100.0
