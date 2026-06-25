from __future__ import annotations

from backend.analytics.strategy_league_table import StrategyLeagueTable


def test_strategy_ranking_grades() -> None:
    table = StrategyLeagueTable().rank_strategies([
        {"strategy_id": "alpha", "win_rate": 0.72, "profit_factor": 1.8, "expectancy": 0.8, "stability": 0.9, "drawdown": 0.08, "sample_size": 40, "recent_trend": 0.4},
        {"strategy_id": "beta", "win_rate": 0.55, "profit_factor": 1.2, "expectancy": 0.3, "stability": 0.7, "drawdown": 0.15, "sample_size": 20, "recent_trend": 0.1},
        {"strategy_id": "gamma", "win_rate": 0.25, "profit_factor": 0.7, "expectancy": -0.4, "stability": 0.3, "drawdown": 0.4, "sample_size": 5, "recent_trend": -0.8},
    ])

    assert table[0]["grade"] in {"PLATINUM", "GOLD"}
    assert table[-1]["grade"] in {"WATCHLIST", "DISABLED"}
