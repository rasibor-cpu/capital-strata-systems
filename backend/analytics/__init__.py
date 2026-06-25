"""Read-only analytics engines for profitability and signal edge observability."""

from .adaptive_position_sizing import AdaptivePositionSizingEngine, AdaptivePositionSizingError
from .closed_loop_learning_engine import ClosedLoopLearningEngine, ClosedLoopLearningEngineError
from .capital_allocation_engine import CapitalAllocationEngine, CapitalAllocationEngineError
from .concentration_guard import ConcentrationGuard, ConcentrationGuardError
from .cost_reality_engine import CostRealityEngine
from .dynamic_acceptance_engine import DynamicAcceptanceEngine, DynamicAcceptanceEngineError
from .execution_selection_engine import ExecutionSelectionEngine, ExecutionSelectionEngineError
from .opportunity_ranking_engine import OpportunityRankingEngine, OpportunityRankingEngineError
from .portfolio_correlation_engine import PortfolioCorrelationEngine, PortfolioCorrelationEngineError
from .profitability_ranking_engine import ProfitabilityRankingEngine, ProfitabilityRankingEngineError
from .portfolio_optimization_engine import PortfolioOptimizationEngine, PortfolioOptimizationError
from .signal_quality_engine import SignalQualityEngine
from .strategy_promotion_engine import StrategyPromotionEngine, StrategyPromotionError
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
    "PortfolioOptimizationEngine",
    "PortfolioOptimizationError",
    "PortfolioCorrelationEngine",
    "PortfolioCorrelationEngineError",
    "StrategyPromotionEngine",
    "StrategyPromotionError",
]
