from __future__ import annotations

from typing import Any

from .adaptive_position_sizing import AdaptivePositionSizingEngine, AdaptivePositionSizingError
from .profitability_ranking_engine import ProfitabilityRankingEngine, ProfitabilityRankingEngineError
from .trade_outcome_repository import TradeOutcomeRepository, TradeOutcomeRepositoryError


class StrategyPromotionError(RuntimeError):
    """Explicit fail-closed exception for strategy promotion recommendations."""


class StrategyPromotionEngine:
    """Recommend strategy promotion, watch, hold, demotion, or disable states."""

    def __init__(
        self,
        repository: TradeOutcomeRepository,
        ranking_engine: ProfitabilityRankingEngine,
        sizing_engine: AdaptivePositionSizingEngine,
    ):
        self.repository = repository
        self.ranking_engine = ranking_engine
        self.sizing_engine = sizing_engine

    def recommend(self) -> list[dict[str, Any]]:
        try:
            outcomes = self.repository.load_outcomes()
        except TradeOutcomeRepositoryError as exc:
            raise StrategyPromotionError(f"Unable to load trade outcomes: {exc}") from exc

        if not outcomes:
            return []

        try:
            rankings = self.ranking_engine.rank_strategies()
        except ProfitabilityRankingEngineError as exc:
            raise StrategyPromotionError(f"Unable to rank strategies: {exc}") from exc

        recommendations: list[dict[str, Any]] = []
        for row in rankings:
            strategy_id = str(row.get("strategy_id", "")).strip()
            if not strategy_id:
                raise StrategyPromotionError("Ranking contains an empty strategy_id")
            trade_count = int(row.get("trade_count", 0))
            realized_pnl = float(row.get("realized_pnl", 0.0))
            win_rate = float(row.get("win_rate", 0.0))
            average_pnl = float(row.get("average_pnl", 0.0))
            score = float(row.get("score", 0.0))
            confidence = min(1.0, max(0.0, trade_count / max(1, trade_count)))
            if trade_count >= 3 and score > 0.0 and win_rate >= 0.5:
                recommendation = "PROMOTE"
            elif trade_count >= 2 and score > 0.0:
                recommendation = "WATCH"
            elif trade_count >= 2 and realized_pnl < 0.0:
                recommendation = "DEMOTE"
            elif trade_count >= 1 and average_pnl < 0.0:
                recommendation = "DISABLE"
            else:
                recommendation = "HOLD"

            recommendations.append(
                {
                    "strategy_id": strategy_id,
                    "realized_pnl": realized_pnl,
                    "win_rate": win_rate,
                    "average_pnl": average_pnl,
                    "trade_count": trade_count,
                    "confidence": confidence,
                    "score": score,
                    "score_trend": "up" if score > 0.0 else "flat",
                    "recommendation": recommendation,
                }
            )

        try:
            self.sizing_engine.size_positions(
                [{"symbol": row["strategy_id"], "allocation_weight": 0.1, "allocation_amount": 100.0, "status": "PREFERRED"} for row in recommendations],
                available_capital=1000.0,
                confidence=0.8,
                maximum_risk_percentage=0.2,
                minimum_trade_size=10.0,
                maximum_trade_size=100.0,
            )
        except AdaptivePositionSizingError:
            raise StrategyPromotionError("Adaptive position sizing failed")

        return recommendations
