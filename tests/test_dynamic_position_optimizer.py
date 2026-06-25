from __future__ import annotations

from backend.analytics.dynamic_position_optimizer import DynamicPositionOptimizer


def test_dynamic_position_optimizer_actions() -> None:
    rows = [
        {
            "strategy_id": "alpha",
            "market_regime": "TREND",
            "strategy_grade": "PLATINUM",
            "expectancy": 0.9,
            "profit_factor": 1.8,
            "drawdown": 0.08,
            "volatility": 0.15,
            "capital_utilization": 0.5,
            "confidence": 0.85,
            "current_position_size": 1000.0,
        },
        {
            "strategy_id": "beta",
            "market_regime": "VOLATILE",
            "strategy_grade": "WATCHLIST",
            "expectancy": -0.2,
            "profit_factor": 0.7,
            "drawdown": 0.3,
            "volatility": 0.5,
            "capital_utilization": 0.9,
            "confidence": 0.3,
            "current_position_size": 1000.0,
        },
    ]
    result = DynamicPositionOptimizer().recommend(rows)
    actions = {row["strategy_id"]: row["action"] for row in result}

    assert actions["alpha"] in {"INCREASE", "KEEP"}
    assert actions["beta"] in {"REDUCE", "KEEP"}
    assert result[0]["strategy_id"] == "alpha"
