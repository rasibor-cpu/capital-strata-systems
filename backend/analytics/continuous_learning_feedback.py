from __future__ import annotations

from typing import Any, Mapping

from .adaptive_calibration_engine import AdaptiveCalibrationEngine
from .learning_pipeline_integration import LearningPipelineIntegration
from .performance_attribution_engine import PerformanceAttributionEngine
from .performance_analytics_engine import PerformanceAnalyticsEngine
from .profitability_ranking_engine import ProfitabilityRankingEngine
from .strategy_league_table import StrategyLeagueTable


class ContinuousLearningFeedbackError(RuntimeError):
    """Fail-closed exception for post-trade learning feedback integration."""


class ContinuousLearningFeedback:
    """Runs canonical post-trade learning updates across analytics and calibration surfaces."""

    def __init__(
        self,
        *,
        learning_pipeline: LearningPipelineIntegration,
        performance_engine: PerformanceAnalyticsEngine | None = None,
        attribution_engine: PerformanceAttributionEngine | None = None,
        calibration_engine: AdaptiveCalibrationEngine | None = None,
        strategy_league_table: StrategyLeagueTable | None = None,
        ranking_engine: ProfitabilityRankingEngine | None = None,
    ) -> None:
        self.learning_pipeline = learning_pipeline
        self.performance_engine = performance_engine or PerformanceAnalyticsEngine()
        self.attribution_engine = attribution_engine or PerformanceAttributionEngine()
        self.calibration_engine = calibration_engine or AdaptiveCalibrationEngine()
        self.strategy_league_table = strategy_league_table or StrategyLeagueTable()
        self.ranking_engine = ranking_engine or ProfitabilityRankingEngine(
            learning_pipeline.trade_outcome_repository,
        )

    def process_completed_trade(
        self,
        completed_trade: Mapping[str, Any],
        *,
        canonical_decision: Mapping[str, Any] | None = None,
        calibration_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(completed_trade, Mapping):
            raise ContinuousLearningFeedbackError("completed_trade must be a mapping")

        learning_result = self.learning_pipeline.write_completed_trade(
            completed_trade,
            canonical_decision=canonical_decision,
        )

        outcomes = self.learning_pipeline.trade_outcome_repository.load_outcomes()
        performance_metrics = self.performance_engine.analyze(outcomes)
        attribution = self.attribution_engine.attribute(outcomes)
        calibration = self.calibration_engine.recommend(
            performance_metrics,
            calibration_state=calibration_state,
        )

        strategy_rankings = self.ranking_engine.rank_strategies()
        strategy_rows = [
            {
                "strategy_id": row.get("strategy_id"),
                "win_rate": row.get("win_rate", 0.0),
                "profit_factor": row.get("score", 0.0) / 100.0,
                "expectancy": row.get("average_pnl", 0.0),
                "drawdown": abs(float(performance_metrics.get("max_drawdown", 0.0) or 0.0)),
                "sample_size": row.get("trade_count", 0),
                "recent_trend": row.get("average_pnl", 0.0),
            }
            for row in strategy_rankings
        ]
        league_table = self.strategy_league_table.rank_strategies(strategy_rows)

        return {
            "learning_result": learning_result,
            "performance_metrics": performance_metrics,
            "attribution": attribution,
            "calibration": calibration,
            "strategy_rankings": strategy_rankings,
            "strategy_league_table": league_table,
        }
