from __future__ import annotations

from backend.analytics.strategy_promotion_manager import StrategyPromotionManager


def test_strategy_promotion_manager_recommendations() -> None:
    recommendations = StrategyPromotionManager().recommend([
        {"strategy_id": "alpha", "grade": "PLATINUM", "sample_size": 30, "recent_trend": 0.2, "drawdown": 0.1},
        {"strategy_id": "beta", "grade": "WATCHLIST", "sample_size": 15, "recent_trend": -0.3, "drawdown": 0.4},
    ])
    rec_map = {row["strategy_id"]: row["recommendation"] for row in recommendations}

    assert rec_map["alpha"] == "PROMOTE"
    assert rec_map["beta"] == "DEMOTE"
