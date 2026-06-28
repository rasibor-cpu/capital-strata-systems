from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class StrategyAllocation:
    """
    Canonical portfolio allocation for a single strategy.

    This class represents the optimizer's recommendation only.
    It does NOT authorize trade execution.
    """

    strategy_id: str
    allocation_percent: float
    allocation_amount: float
    confidence: float
    expected_risk: float
    rationale: str = ""


@dataclass(slots=True)
class PortfolioAllocationPlan:
    """
    Canonical output of the Portfolio Optimizer.

    The Portfolio Optimizer recommends allocations.
    Downstream governance components remain responsible for validating
    and approving execution.
    """

    generated_at: str
    market_regime: str
    risk_profile: str
    total_capital: float
    allocations: List[StrategyAllocation] = field(default_factory=list)
    diversification_metrics: Dict[str, Any] = field(default_factory=dict)
    validation_status: str = "PENDING"

    def total_allocated_percent(self) -> float:
        return round(
            sum(item.allocation_percent for item in self.allocations),
            4,
        )

    def total_allocated_amount(self) -> float:
        return round(
            sum(item.allocation_amount for item in self.allocations),
            2,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "market_regime": self.market_regime,
            "risk_profile": self.risk_profile,
            "total_capital": self.total_capital,
            "validation_status": self.validation_status,
            "allocations": [
                {
                    "strategy_id": item.strategy_id,
                    "allocation_percent": item.allocation_percent,
                    "allocation_amount": item.allocation_amount,
                    "confidence": item.confidence,
                    "expected_risk": item.expected_risk,
                    "rationale": item.rationale,
                }
                for item in self.allocations
            ],
            "diversification_metrics": self.diversification_metrics,
            "total_allocated_percent": self.total_allocated_percent(),
            "total_allocated_amount": self.total_allocated_amount(),
        }
