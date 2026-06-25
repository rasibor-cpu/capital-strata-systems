from __future__ import annotations

from backend.analytics.autonomous_profitability_program import AutonomousProfitabilityProgram


def test_autonomous_profitability_program_cycle() -> None:
    program = AutonomousProfitabilityProgram()

    result = program.optimize_cycle(
        completed_trades=[
            {
                "trade_id": "t1",
                "symbol": "AAPL",
                "asset_class": "EQUITY",
                "strategy_id": "alpha",
                "market_regime": "TRENDING",
                "confidence": 0.8,
                "quality_score": 82.0,
                "realized_pnl": 8.0,
                "holding_duration_seconds": 300.0,
                "risk": 4.0,
            },
            {
                "trade_id": "t2",
                "symbol": "MSFT",
                "asset_class": "EQUITY",
                "strategy_id": "beta",
                "market_regime": "RANGING",
                "confidence": 0.6,
                "quality_score": 65.0,
                "realized_pnl": 2.0,
                "holding_duration_seconds": 300.0,
                "risk": 3.0,
            },
        ],
        strategy_league_table=[
            {"strategy_id": "alpha", "grade": "PLATINUM", "sample_size": 20, "recent_trend": 0.2, "drawdown": 0.1},
            {"strategy_id": "beta", "grade": "SILVER", "sample_size": 12, "recent_trend": 0.1, "drawdown": 0.15},
        ],
        position_context=[
            {
                "strategy_id": "alpha",
                "market_regime": "TRENDING",
                "strategy_grade": "PLATINUM",
                "expectancy": 0.7,
                "profit_factor": 1.6,
                "drawdown": 0.1,
                "volatility": 0.2,
                "capital_utilization": 0.5,
                "confidence": 0.8,
                "current_position_size": 1000.0,
            }
        ],
        allocation_rows=[
            {"symbol": "AAPL", "asset_class": "EQUITY", "strategy_id": "alpha", "allocation_weight": 0.6},
            {"symbol": "MSFT", "asset_class": "EQUITY", "strategy_id": "beta", "allocation_weight": 0.4},
        ],
        sizing_rows=[
            {"symbol": "AAPL", "recommended_position_size": 0.4},
            {"symbol": "MSFT", "recommended_position_size": 0.2},
        ],
        strategy_rows=[
            {"symbol": "AAPL", "recommendation": "PROMOTE"},
            {"symbol": "MSFT", "recommendation": "HOLD"},
        ],
        asset_class_exposure_limits={"EQUITY": 1.0},
        max_symbol_exposure=0.7,
        max_total_allocation=1.0,
        backtesting_results={"backtest_decision": "ACCEPT", "performance_summary": {"expectancy": 0.11, "profit_factor": 1.2}},
        validation_results={"summary": {"SAFE": 2, "REVIEW": 0, "REJECT": 0}},
        readiness_assessment={"readiness": "READY"},
    )

    assert "optimization_report" in result
    assert "unified_optimization_summary" in result
    assert result["unified_optimization_summary"]["best_strategy"] in {"alpha", "UNKNOWN"}
    assert "portfolio_health" in result["unified_optimization_summary"]
