from __future__ import annotations

from backend.analytics.profitability_optimizer import ProfitabilityOptimizer


def test_profitability_optimizer_package() -> None:
    package = ProfitabilityOptimizer().optimize(
        completed_trades=[
            {"strategy_id": "alpha", "asset_class": "EQUITY", "market_regime": "TREND", "confidence": 0.8, "quality_score": 82.0, "realized_pnl": 8.0},
            {"strategy_id": "beta", "asset_class": "FX", "market_regime": "VOLATILE", "confidence": 0.4, "quality_score": 40.0, "realized_pnl": -3.0},
        ],
        strategy_league_table=[
            {"strategy_id": "alpha", "grade": "PLATINUM", "sample_size": 20, "recent_trend": 0.2, "drawdown": 0.1},
            {"strategy_id": "beta", "grade": "WATCHLIST", "sample_size": 10, "recent_trend": -0.3, "drawdown": 0.35},
        ],
        position_context=[
            {"strategy_id": "alpha", "market_regime": "TREND", "strategy_grade": "PLATINUM", "expectancy": 0.8, "profit_factor": 1.6, "drawdown": 0.1, "volatility": 0.2, "capital_utilization": 0.5, "confidence": 0.8, "current_position_size": 1000.0}
        ],
    )

    assert "recommended_threshold_changes" in package
    assert "recommended_sizing_changes" in package
    assert "recommended_strategy_changes" in package
    assert "recommended_regime_changes" in package
    assert package["metadata"]["recommendation_only"] is True
