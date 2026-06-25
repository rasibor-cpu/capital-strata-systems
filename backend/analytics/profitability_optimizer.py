from __future__ import annotations

from typing import Any, Mapping

from .adaptive_threshold_calibration_engine import AdaptiveThresholdCalibrationEngine
from .dynamic_position_optimizer import DynamicPositionOptimizer
from .regime_parameter_profiles import RegimeParameterProfiles
from .strategy_promotion_manager import StrategyPromotionManager


class ProfitabilityOptimizerError(RuntimeError):
    """Fail-closed exception for profitability optimization packaging."""


class ProfitabilityOptimizer:
    """Produce recommendation-only optimization packages from operational evidence."""

    def __init__(
        self,
        *,
        threshold_engine: AdaptiveThresholdCalibrationEngine | None = None,
        position_optimizer: DynamicPositionOptimizer | None = None,
        regime_profiles: RegimeParameterProfiles | None = None,
        promotion_manager: StrategyPromotionManager | None = None,
    ) -> None:
        self.threshold_engine = threshold_engine or AdaptiveThresholdCalibrationEngine()
        self.position_optimizer = position_optimizer or DynamicPositionOptimizer()
        self.regime_profiles = regime_profiles or RegimeParameterProfiles()
        self.promotion_manager = promotion_manager or StrategyPromotionManager()

    def optimize(
        self,
        *,
        completed_trades: list[Mapping[str, Any]] | None,
        strategy_league_table: list[Mapping[str, Any]] | None,
        position_context: list[Mapping[str, Any]] | None,
        current_thresholds: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if completed_trades is not None and not isinstance(completed_trades, list):
            raise ProfitabilityOptimizerError("completed_trades must be a list when provided")
        if strategy_league_table is not None and not isinstance(strategy_league_table, list):
            raise ProfitabilityOptimizerError("strategy_league_table must be a list when provided")
        if position_context is not None and not isinstance(position_context, list):
            raise ProfitabilityOptimizerError("position_context must be a list when provided")
        if current_thresholds is not None and not isinstance(current_thresholds, Mapping):
            raise ProfitabilityOptimizerError("current_thresholds must be a mapping when provided")

        trades = list(completed_trades or [])
        league = list(strategy_league_table or [])
        positions = list(position_context or [])

        threshold_recommendations = self.threshold_engine.recommend(trades, current_thresholds=current_thresholds)
        sizing_recommendations = self.position_optimizer.recommend(positions)
        strategy_recommendations = self.promotion_manager.recommend(league)
        regime_recommendations = self.regime_profiles.recommend_profiles()

        estimated_improvement = self._estimate_improvement(trades, strategy_recommendations)
        confidence_score = self._confidence_score(trades, league, sizing_recommendations)

        return {
            "recommended_threshold_changes": threshold_recommendations,
            "recommended_sizing_changes": sizing_recommendations,
            "recommended_strategy_changes": strategy_recommendations,
            "recommended_regime_changes": regime_recommendations,
            "estimated_improvement": round(estimated_improvement, 8),
            "confidence_score": round(confidence_score, 8),
            "metadata": {
                "trade_count": len(trades),
                "strategy_count": len(league),
                "position_rows": len(positions),
                "recommendation_only": True,
            },
        }

    def _estimate_improvement(self, trades: list[Mapping[str, Any]], strategy_recommendations: list[Mapping[str, Any]]) -> float:
        if not trades:
            return 0.0
        avg_pnl = sum(self._float(row.get("realized_pnl", row.get("pnl", 0.0))) for row in trades) / len(trades)
        promote_count = sum(1 for row in strategy_recommendations if str(row.get("recommendation", "")) == "PROMOTE")
        demote_count = sum(1 for row in strategy_recommendations if str(row.get("recommendation", "")) in {"DEMOTE", "DISABLE"})
        return avg_pnl * (1.0 + (0.10 * promote_count) - (0.05 * demote_count))

    def _confidence_score(
        self,
        trades: list[Mapping[str, Any]],
        league: list[Mapping[str, Any]],
        sizing_recommendations: list[Mapping[str, Any]],
    ) -> float:
        trade_conf = self._clamp01(len(trades) / 100.0)
        league_conf = self._clamp01(len(league) / 20.0)
        sizing_keep_ratio = (
            sum(1 for row in sizing_recommendations if str(row.get("action", "")) == "KEEP") / len(sizing_recommendations)
            if sizing_recommendations
            else 0.5
        )
        return (0.45 * trade_conf) + (0.30 * league_conf) + (0.25 * sizing_keep_ratio)

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
