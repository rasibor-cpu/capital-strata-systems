from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.intelligence.unified_opportunity import UnifiedOpportunity


@dataclass
class OpportunityViabilityResult:
    viable: bool = False
    reasons: List[str] = field(default_factory=list)
    adjusted_edge: float = 0.0
    risk_flags: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class OpportunityViabilityEngine:
    def __init__(
        self,
        min_signal_strength: float = 0.5,
        max_spread_score: float = 50.0,
        max_estimated_cost: float = 30.0,
        min_liquidity: float = 0.0,
        min_volatility: float = 0.0,
        max_volatility: float = 100.0,
    ) -> None:
        self.min_signal_strength = min_signal_strength
        self.max_spread_score = max_spread_score
        self.max_estimated_cost = max_estimated_cost
        self.min_liquidity = min_liquidity
        self.min_volatility = min_volatility
        self.max_volatility = max_volatility

    def evaluate(self, opportunity: UnifiedOpportunity) -> OpportunityViabilityResult:
        reasons: List[str] = []
        risk_flags: List[str] = []

        if opportunity.signal_strength < self.min_signal_strength:
            reasons.append("signal_strength_below_minimum")
        if opportunity.spread_score > self.max_spread_score:
            reasons.append("spread_score_above_sanity_bound")
        if opportunity.estimated_cost > self.max_estimated_cost:
            reasons.append("estimated_cost_above_sanity_bound")
        if opportunity.liquidity_score < self.min_liquidity:
            reasons.append("liquidity_below_minimum")
        if not (self.min_volatility <= opportunity.volatility_score <= self.max_volatility):
            reasons.append("volatility_out_of_bounds")

        if opportunity.estimated_slippage > self.max_estimated_cost:
            risk_flags.append("high_estimated_slippage")
        if opportunity.expected_edge <= 0.0:
            risk_flags.append("non_positive_edge")

        penalty = max(0.0, opportunity.estimated_cost + opportunity.estimated_slippage)
        adjusted_edge = opportunity.expected_edge - penalty

        return OpportunityViabilityResult(
            viable=len(reasons) == 0,
            reasons=reasons,
            adjusted_edge=adjusted_edge,
            risk_flags=risk_flags,
            diagnostics={
                "signal_strength": opportunity.signal_strength,
                "spread_score": opportunity.spread_score,
                "estimated_cost": opportunity.estimated_cost,
                "estimated_slippage": opportunity.estimated_slippage,
                "liquidity_score": opportunity.liquidity_score,
                "volatility_score": opportunity.volatility_score,
            },
        )
