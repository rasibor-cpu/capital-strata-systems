"""Read-only analytics engines for profitability and signal edge observability."""

from .cost_reality_engine import CostRealityEngine
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
    "CostRealityEngine",
    "SignalQualityEngine",
    "TradeOutcomeAnalyticsEngine",
    "DuplicateTradeOutcomeError",
    "TradeOutcomeRecord",
    "TradeOutcomeRepository",
    "TradeOutcomeRepositoryError",
    "build_trade_outcome_analytics_adapter",
    "persist_completed_trade_outcome",
]
