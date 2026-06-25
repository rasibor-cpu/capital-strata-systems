from __future__ import annotations

from backend.analytics.marathon_readiness_optimizer import MarathonReadinessOptimizer


def test_marathon_readiness_optimizer_scores() -> None:
    result = MarathonReadinessOptimizer().assess(
        optimization_package={"estimated_improvement": 1.2, "confidence_score": 0.78},
        backtesting_result={"baseline_drawdown": 4.0, "optimized_drawdown": 3.8},
        validation_result={"summary": {"SAFE": 6, "REVIEW": 1, "REJECT": 0}},
        health_summary={"status": "HEALTHY"},
    )

    assert 0.0 <= result["optimization_readiness_score"] <= 1.0
    assert 0.0 <= result["optimization_risk_score"] <= 1.0
    assert result["readiness"] in {"READY", "CONDITIONAL", "NOT_READY"}
