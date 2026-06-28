from analytics.strategy_aware_portfolio_optimizer import StrategyAwarePortfolioOptimizer


class FakeRankingEngine:
    def __init__(self, rankings):
        self._rankings = rankings

    def rank_by_entry_reason(self):
        return self._rankings


def test_strategy_aware_optimizer_prefers_promoted_strategies():
    optimizer = StrategyAwarePortfolioOptimizer(
        ranking_engine=FakeRankingEngine(
            {
                "trend_following": {"lifecycle_recommendation": "PROMOTE"},
                "mean_reversion": {"lifecycle_recommendation": "WATCH"},
                "weak_signal": {"lifecycle_recommendation": "DEMOTE"},
            }
        )
    )

    plan = optimizer.build_plan(total_capital=1000.0)

    assert len(plan.allocations) == 1
    assert plan.allocations[0].strategy_id == "trend_following"
    assert plan.allocations[0].allocation_percent == 100.0
    assert plan.allocations[0].allocation_amount == 1000.0


def test_strategy_aware_optimizer_falls_back_to_all_ranked_strategies():
    optimizer = StrategyAwarePortfolioOptimizer(
        ranking_engine=FakeRankingEngine(
            {
                "mean_reversion": {"lifecycle_recommendation": "WATCH"},
                "carry_trade": {"lifecycle_recommendation": "NEUTRAL"},
            }
        )
    )

    plan = optimizer.build_plan(total_capital=2000.0)

    assert len(plan.allocations) == 2
    assert [item.strategy_id for item in plan.allocations] == [
        "mean_reversion",
        "carry_trade",
    ]
    assert plan.total_allocated_percent() == 100.0
    assert plan.total_allocated_amount() == 2000.0


def test_strategy_aware_optimizer_returns_empty_plan_when_no_rankings_exist():
    optimizer = StrategyAwarePortfolioOptimizer(
        ranking_engine=FakeRankingEngine({})
    )

    plan = optimizer.build_plan(total_capital=1500.0)

    assert len(plan.allocations) == 0
    assert plan.total_allocated_percent() == 0.0
    assert plan.total_allocated_amount() == 0.0
