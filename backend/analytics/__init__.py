"""Read-only analytics engines for profitability and signal edge observability."""

from .adaptive_position_sizing import AdaptivePositionSizingEngine, AdaptivePositionSizingError
from .adaptive_calibration_engine import AdaptiveCalibrationEngine, AdaptiveCalibrationEngineError
from .improvement_recommendation_engine import ImprovementRecommendationEngine, ImprovementRecommendationEngineError
from .closed_loop_learning_engine import ClosedLoopLearningEngine, ClosedLoopLearningEngineError
from .capital_allocation_engine import CapitalAllocationEngine, CapitalAllocationEngineError
from .concentration_guard import ConcentrationGuard, ConcentrationGuardError
from .cost_reality_engine import CostRealityEngine
from .dynamic_acceptance_engine import DynamicAcceptanceEngine, DynamicAcceptanceEngineError
from .execution_selection_engine import ExecutionSelectionEngine, ExecutionSelectionEngineError
from .opportunity_cost_engine import OpportunityCostEngine, OpportunityCostEngineError
from .performance_attribution_engine import PerformanceAttributionEngine, PerformanceAttributionEngineError
from .performance_analytics_engine import PerformanceAnalyticsEngine, PerformanceAnalyticsEngineError
from .performance_reporting_engine import PerformanceReportingEngine, PerformanceReportingEngineError
from .opportunity_ranking_engine import OpportunityRankingEngine, OpportunityRankingEngineError
from .portfolio_correlation_engine import PortfolioCorrelationEngine, PortfolioCorrelationEngineError
from .profitability_ranking_engine import ProfitabilityRankingEngine, ProfitabilityRankingEngineError
from .portfolio_optimization_engine import PortfolioOptimizationEngine, PortfolioOptimizationError
from .signal_quality_engine import SignalQualityEngine
from .strategy_league_table import StrategyLeagueTable, StrategyLeagueTableError
from .strategy_promotion_engine import StrategyPromotionEngine, StrategyPromotionError
from .trade_explanation_repository import TradeExplanationRepository, TradeExplanationRepositoryError
from .trade_forensics_engine import TradeForensicsEngine, TradeForensicsEngineError
from .trade_quality_models import TradeQualityAssessment
from .trade_quality_scoring_engine import TradeQualityScoringEngine, TradeQualityScoringEngineError
from .trade_outcome_analytics_engine import TradeOutcomeAnalyticsEngine
from .trade_outcome_repository import (
    DuplicateTradeOutcomeError,
    TradeOutcomeRecord,
    TradeOutcomeRepository,
    TradeOutcomeRepositoryError,
    build_trade_outcome_analytics_adapter,
    persist_completed_trade_outcome,
)

__all__ = [
    "AdaptivePositionSizingEngine",
    "AdaptivePositionSizingError",
    "AdaptiveCalibrationEngine",
    "AdaptiveCalibrationEngineError",
    "ImprovementRecommendationEngine",
    "ImprovementRecommendationEngineError",
    "ClosedLoopLearningEngine",
    "ClosedLoopLearningEngineError",
    "CapitalAllocationEngine",
    "CapitalAllocationEngineError",
    "ConcentrationGuard",
    "ConcentrationGuardError",
    "CostRealityEngine",
    "DynamicAcceptanceEngine",
    "DynamicAcceptanceEngineError",
    "ExecutionSelectionEngine",
    "ExecutionSelectionEngineError",
    "OpportunityCostEngine",
    "OpportunityCostEngineError",
    "PerformanceAttributionEngine",
    "PerformanceAttributionEngineError",
    "PerformanceAnalyticsEngine",
    "PerformanceAnalyticsEngineError",
    "PerformanceReportingEngine",
    "PerformanceReportingEngineError",
    "OpportunityRankingEngine",
    "OpportunityRankingEngineError",
    "ProfitabilityRankingEngine",
    "ProfitabilityRankingEngineError",
    "SignalQualityEngine",
    "TradeQualityAssessment",
    "TradeQualityScoringEngine",
    "TradeQualityScoringEngineError",
    "TradeOutcomeAnalyticsEngine",
    "DuplicateTradeOutcomeError",
    "TradeOutcomeRecord",
    "TradeOutcomeRepository",
    "TradeOutcomeRepositoryError",
    "build_trade_outcome_analytics_adapter",
    "persist_completed_trade_outcome",
    "StrategyLeagueTable",
    "StrategyLeagueTableError",
    "PortfolioOptimizationEngine",
    "PortfolioOptimizationError",
    "PortfolioCorrelationEngine",
    "PortfolioCorrelationEngineError",
    "StrategyPromotionEngine",
    "StrategyPromotionError",
    "TradeExplanationRepository",
    "TradeExplanationRepositoryError",
    "TradeForensicsEngine",
    "TradeForensicsEngineError",
]
