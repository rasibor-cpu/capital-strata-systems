"""Read-only analytics engines for profitability and signal edge observability."""

from .capital_allocation_engine import CapitalAllocationEngine, CapitalAllocationEngineError
from .cost_reality_engine import CostRealityEngine
from .profitability_ranking_engine import ProfitabilityRankingEngine, ProfitabilityRankingEngineError
from .signal_quality_engine import SignalQualityEngine
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
    "CapitalAllocationEngine",
    "CapitalAllocationEngineError",
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
]
