from analytics.portfolio_optimizer_engine import PortfolioOptimizerEngine


def test_confidence_weighting_prefers_high_confidence():
    engine = PortfolioOptimizerEngine()

    strategies = [
        {"strategy_id": "trend_following", "confidence": 0.95},
        {"strategy_id": "mean_reversion", "confidence": 0.60},
        {"strategy_id": "momentum_breakout", "confidence": 0.85},
    ]

    plan = engine.build_confidence_weighted_plan(
        strategies,
        total_capital=1000.0,
        market_regime="TRENDING",
        risk_profile="BALANCED",
    )

    allocations = {a.strategy_id: a.allocation_percent for a in plan.allocations}

    assert allocations["trend_following"] > allocations["momentum_breakout"]
    assert allocations["momentum_breakout"] > allocations["mean_reversion"]
    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 1000.0


def test_missing_confidence_defaults_safely():
    engine = PortfolioOptimizerEngine()

    strategies = [
        {"strategy_id": "A"},
        {"strategy_id": "B"},
    ]

    plan = engine.build_confidence_weighted_plan(
        strategies,
        total_capital=200.0,
    )

    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 200.0
