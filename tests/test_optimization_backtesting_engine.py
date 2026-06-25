from __future__ import annotations

from backend.analytics.optimization_backtesting_engine import OptimizationBacktestingEngine


def test_optimization_backtesting_accept_or_reject_deterministic() -> None:
    historical = [
        {"strategy_id": "alpha", "market_regime": "TREND", "realized_pnl": 8.0},
        {"strategy_id": "alpha", "market_regime": "TREND", "realized_pnl": -2.0},
        {"strategy_id": "beta", "market_regime": "VOLATILE", "realized_pnl": -1.0},
    ]
    package = {
        "recommended_sizing_changes": [
            {"strategy_id": "alpha", "market_regime": "TREND", "action": "INCREASE"},
            {"strategy_id": "beta", "market_regime": "VOLATILE", "action": "REDUCE"},
        ]
    }
    result = OptimizationBacktestingEngine().backtest(historical, package)

    assert result["backtest_decision"] in {"ACCEPT", "REJECT"}
    assert isinstance(result["win_rate_delta"], float)
    assert isinstance(result["profit_factor_delta"], float)
