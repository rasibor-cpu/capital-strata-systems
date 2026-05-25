from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.analytics import (
    CostRealityEngine,
    SignalQualityEngine,
    TradeOutcomeAnalyticsEngine,
)


class AnalyticsStateBuilder:
    """Aggregates read-only analytics into dashboard-safe render payloads."""

    def __init__(self) -> None:
        self.trade_outcome_engine = TradeOutcomeAnalyticsEngine()
        self.cost_reality_engine = CostRealityEngine()
        self.signal_quality_engine = SignalQualityEngine()

    def build(
        self,
        execution_history: list[Mapping[str, Any]] | None = None,
        opportunities: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        trades = execution_history or []
        signals = opportunities or []

        trade_outcome = self.trade_outcome_engine.build(trades)
        cost_reality = self.cost_reality_engine.build(trades)
        signal_quality = self.signal_quality_engine.build(signals)

        return {
            "trade_outcome": trade_outcome,
            "cost_reality": cost_reality,
            "signal_quality": signal_quality,
            "headline": {
                "expectancy": float(trade_outcome.get("expectancy", 0.0)),
                "profit_factor": float(trade_outcome.get("profit_factor", 0.0)),
                "estimated_execution_cost": float(
                    cost_reality.get("cost_components", {}).get("total_estimated_cost", 0.0)
                ),
                "signal_quality": float(signal_quality.get("signal_score", 0.0)),
                "current_edge_estimate": float(cost_reality.get("net_edge_estimate", 0.0)),
                "drawdown_state": float(trade_outcome.get("max_drawdown", 0.0)),
            },
        }
