from __future__ import annotations

from backend.analytics.marathon_readiness_optimizer import MarathonReadinessOptimizer
from backend.analytics.optimization_backtesting_engine import OptimizationBacktestingEngine
from backend.analytics.optimization_summary_report import OptimizationSummaryReport
from backend.analytics.optimization_validation_engine import OptimizationValidationEngine
from backend.analytics.profitability_optimizer import ProfitabilityOptimizer


def test_optimization_pipeline_end_to_end() -> None:
    optimizer = ProfitabilityOptimizer()
    package = optimizer.optimize(
        completed_trades=[
            {"strategy_id": "alpha", "asset_class": "EQUITY", "market_regime": "TREND", "confidence": 0.82, "quality_score": 88.0, "realized_pnl": 9.0},
            {"strategy_id": "beta", "asset_class": "FX", "market_regime": "VOLATILE", "confidence": 0.35, "quality_score": 40.0, "realized_pnl": -2.5},
        ],
        strategy_league_table=[
            {"strategy_id": "alpha", "grade": "PLATINUM", "sample_size": 25, "recent_trend": 0.3, "drawdown": 0.09},
            {"strategy_id": "beta", "grade": "WATCHLIST", "sample_size": 12, "recent_trend": -0.2, "drawdown": 0.32},
        ],
        position_context=[
            {"strategy_id": "alpha", "market_regime": "TREND", "strategy_grade": "PLATINUM", "expectancy": 0.9, "profit_factor": 1.7, "drawdown": 0.1, "volatility": 0.2, "capital_utilization": 0.55, "confidence": 0.85, "current_position_size": 1000.0},
            {"strategy_id": "beta", "market_regime": "VOLATILE", "strategy_grade": "WATCHLIST", "expectancy": -0.1, "profit_factor": 0.8, "drawdown": 0.3, "volatility": 0.45, "capital_utilization": 0.85, "confidence": 0.4, "current_position_size": 1000.0},
        ],
    )

    backtest = OptimizationBacktestingEngine().backtest(
        historical_trades=[
            {"strategy_id": "alpha", "market_regime": "TREND", "realized_pnl": 8.0},
            {"strategy_id": "alpha", "market_regime": "TREND", "realized_pnl": -2.0},
            {"strategy_id": "beta", "market_regime": "VOLATILE", "realized_pnl": -1.0},
        ],
        optimization_package=package,
    )
    validation = OptimizationValidationEngine().validate(package, backtest)
    readiness = MarathonReadinessOptimizer().assess(
        optimization_package=package,
        backtesting_result=backtest,
        validation_result=validation,
        health_summary={"status": "HEALTHY"},
    )
    report = OptimizationSummaryReport().build(
        optimization_package=package,
        backtesting_results=backtest,
        validation_results=validation,
        readiness_assessment=readiness,
    )

    assert report["optimization_summary"]["metadata"]["recommendation_only"] is True
    assert report["certification_recommendation"] in {"GO", "CONDITIONAL_GO", "NO_GO"}
    assert backtest["backtest_decision"] in {"ACCEPT", "REJECT"}
