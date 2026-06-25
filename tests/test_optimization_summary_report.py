from __future__ import annotations

from backend.analytics.optimization_summary_report import OptimizationSummaryReport


def test_optimization_summary_report_build() -> None:
    report = OptimizationSummaryReport().build(
        optimization_package={
            "estimated_improvement": 1.3,
            "confidence_score": 0.8,
            "metadata": {
                "trade_count": 10,
                "best_strategy": "alpha",
                "expectancy": 0.12,
                "profit_factor": 1.45,
                "max_drawdown": 0.08,
                "learning_confidence": 0.77,
                "capital_efficiency": 0.66,
                "market_regime": "TRENDING",
            },
            "recommended_threshold_changes": {"strategy_thresholds": []},
            "recommended_sizing_changes": [],
            "recommended_strategy_changes": [{"strategy_id": "alpha", "recommendation": "PROMOTE"}],
            "recommended_regime_changes": {"TREND": {"confidence_threshold": 0.6}},
        },
        backtesting_results={"backtest_decision": "ACCEPT"},
        validation_results={"summary": {"SAFE": 5, "REVIEW": 0, "REJECT": 0}},
        readiness_assessment={"readiness": "READY"},
    )

    assert report["certification_recommendation"] == "GO"
    assert report["optimization_summary"]["metadata"]["trade_count"] == 10
    assert report["optimization_summary"]["best_strategy"] == "alpha"
    assert report["optimization_summary"]["market_regime"] == "TRENDING"
    assert report["optimization_summary"]["portfolio_health"] == "STABLE"
