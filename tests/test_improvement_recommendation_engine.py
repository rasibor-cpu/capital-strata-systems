from __future__ import annotations

from backend.analytics.improvement_recommendation_engine import ImprovementRecommendationEngine


def test_improvement_recommendations() -> None:
    recommendations = ImprovementRecommendationEngine().recommend(
        performance_summary={"win_rate": 0.42, "profit_factor": 0.9, "max_drawdown": 0.25, "exit_confidence": 0.5},
        strategy_league_table=[{"strategy_id": "alpha", "grade": "WATCHLIST", "sample_size": 10}, {"strategy_id": "beta", "grade": "GOLD", "sample_size": 30}],
        opportunity_cost={"summary": {"rejected_trade_count": 2, "missed_opportunity_total": 12.0}, "opportunity_costs": [{"threshold_implication": "relax_acceptance_threshold"}]},
        attribution={"market_regime": [{"market_regime": "RANGING", "win_rate": 0.3}]},
        health_summary={"status": "WARNING"},
    )

    actions = {item["action"] for item in recommendations}
    assert "reduce allocation" in actions
    assert "pause weak strategy" in actions
    assert "relax acceptance threshold" in actions
    assert "reduce exposure in weak regime" in actions
