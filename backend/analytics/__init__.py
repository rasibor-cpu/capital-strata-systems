"""Read-only analytics engines for profitability and signal edge observability."""

from .adaptive_position_sizing import AdaptivePositionSizingEngine, AdaptivePositionSizingError
from .capital_allocation_engine import CapitalAllocationEngine, CapitalAllocationEngineError
from .concentration_guard import ConcentrationGuard, ConcentrationGuardError
from .cost_reality_engine import CostRealityEngine
from .portfolio_correlation_engine import PortfolioCorrelationEngine, PortfolioCorrelationEngineError
from .profitability_ranking_engine import ProfitabilityRankingEngine, ProfitabilityRankingEngineError
from .portfolio_optimization_engine import PortfolioOptimizationEngine, PortfolioOptimizationError
from .signal_quality_engine import SignalQualityEngine
from .strategy_promotion_engine import StrategyPromotionEngine, StrategyPromotionError
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
    "CapitalAllocationEngine",
    "CapitalAllocationEngineError",
    "ConcentrationGuard",
    "ConcentrationGuardError",
    "CostRealityEngine",
    "ProfitabilityRankingEngine",
    "ProfitabilityRankingEngineError",
    "SignalQualityEngine",
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
