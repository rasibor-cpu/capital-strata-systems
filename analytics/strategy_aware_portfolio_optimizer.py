from __future__ import annotations

from typing import Any, Dict

from analytics.portfolio_optimizer import PortfolioAllocationPlan
from analytics.portfolio_optimizer_engine import PortfolioOptimizerEngine
from analytics.strategy_ranking_engine import StrategyRankingEngine


class StrategyAwarePortfolioOptimizer:
    """
    Phase 129B-3

    Bridges the StrategyRankingEngine and the deterministic
    PortfolioOptimizerEngine.

    For the initial implementation, only strategies with a
    lifecycle recommendation of "PROMOTE" are selected.
    If none qualify, the optimizer falls back to all known
    strategy labels.
    """

    def __init__(self, ranking_engine: StrategyRankingEngine | None = None):
        self.ranking_engine = ranking_engine or StrategyRankingEngine()
        self.optimizer = PortfolioOptimizerEngine()

    def build_plan(
        self,
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        rankings: Dict[str, Any] = self.ranking_engine.rank_by_entry_reason()

        promote = [
            name
            for name, stats in rankings.items()
            if stats.get("lifecycle_recommendation") == "PROMOTE"
        ]

        strategy_ids = promote if promote else list(rankings.keys())

        return self.optimizer.build_equal_weight_plan(
            strategy_ids,
            total_capital=total_capital,
            market_regime=market_regime,
            risk_profile=risk_profile,
        )
