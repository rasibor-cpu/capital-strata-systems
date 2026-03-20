from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ExecutionCost:
    spread: float
    slippage: float
    fees: float

    @property
    def total(self) -> float:
        return self.spread + self.slippage + self.fees


class ExecutionCostEngine:
    """
    CSS Execution Cost Engine

    Purpose:
    - Estimate real-world execution cost BEFORE trade approval
    - Feed into decision layer (TradeDecisionOrchestrator)
    - Prevent low-quality trades from passing due to hidden costs

    Phase 1:
    - Static / heuristic-based cost model
    - No live broker dependency
    """

    def __init__(self):
        self.default_spread = 0.0002
        self.default_slippage = 0.0003
        self.default_fee_rate = 0.0001

    def estimate_cost(
        self,
        price: float,
        notional: float,
        volatility: float,
        liquidity_score: float,
    ) -> ExecutionCost:
        spread = self._estimate_spread(liquidity_score)
        slippage = self._estimate_slippage(volatility, liquidity_score)
        fees = self._estimate_fees(notional)

        return ExecutionCost(
            spread=spread,
            slippage=slippage,
            fees=fees,
        )

    def _estimate_spread(self, liquidity_score: float) -> float:
        return self.default_spread * (1 + (1 - liquidity_score))

    def _estimate_slippage(self, volatility: float, liquidity_score: float) -> float:
        return self.default_slippage * (1 + volatility) * (1 + (1 - liquidity_score))

    def _estimate_fees(self, notional: float) -> float:
        return notional * self.default_fee_rate

    def evaluate_trade_viability(
        self,
        expected_edge: float,
        cost: ExecutionCost,
    ) -> Dict[str, float]:
        net_edge = expected_edge - cost.total

        return {
            "expected_edge": expected_edge,
            "total_cost": cost.total,
            "net_edge": net_edge,
            "viable": net_edge > 0,
        }
