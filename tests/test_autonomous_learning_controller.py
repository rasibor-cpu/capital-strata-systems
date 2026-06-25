from __future__ import annotations

from backend.analytics.autonomous_learning_controller import AutonomousLearningController


def test_autonomous_learning_controller_build_package() -> None:
    package = AutonomousLearningController().build_learning_package(
        trade_forensics=[{"trade_id": "t2", "decision_optimal": False}, {"trade_id": "t1", "decision_optimal": True}],
        performance_attribution={"market_regime": [{"market_regime": "TREND", "win_rate": 0.62}]},
        opportunity_cost={"summary": {"missed_opportunity_total": 9.0}},
        strategy_league_table=[{"strategy_id": "alpha", "grade": "GOLD"}],
        improvement_recommendations=[{"action": "adjust threshold"}],
    )

    assert package["learning_summary"]["trade_count"] == 2
    assert package["learning_summary"]["top_strategy"] == "alpha"
    assert package["learning_priority"] in {"MEDIUM", "HIGH"}
