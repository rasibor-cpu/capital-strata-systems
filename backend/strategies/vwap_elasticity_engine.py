from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class VWAPElasticityResult:
    symbol: str
    mid_price: float
    vwap: float
    deviation_pct: float
    elasticity_score: float
    elasticity_state: str
    reversion_signal: bool


class VWAPElasticityEngine:
    """
    VWAP Elasticity Engine

    Purpose:
    - Measure how far price has stretched away from VWAP
    - Quantify mean-reversion opportunity strength
    - Provide structured signal to TradeDecisionOrchestrator

    Core idea:
    - Small deviation → weak signal
    - Moderate deviation → actionable
    - Extreme deviation → high-probability snap-back zone
    """

    def __init__(
        self,
        elite_threshold: float = 0.022,     # 2.2%
        extreme_threshold: float = 0.028,   # 2.8%
    ):
        self.elite_threshold = elite_threshold
        self.extreme_threshold = extreme_threshold

    def evaluate(
        self,
        symbol: str,
        mid_price: float,
        vwap: float,
    ) -> VWAPElasticityResult:

        if vwap <= 0:
            return VWAPElasticityResult(
                symbol=symbol,
                mid_price=mid_price,
                vwap=vwap,
                deviation_pct=0.0,
                elasticity_score=0.0,
                elasticity_state="invalid",
                reversion_signal=False,
            )

        deviation_pct = (mid_price - vwap) / vwap

        abs_dev = abs(deviation_pct)

        # Elasticity scoring logic
        if abs_dev < 0.005:
            elasticity_state = "flat"
            elasticity_score = 0.1

        elif abs_dev < 0.012:
            elasticity_state = "building"
            elasticity_score = 0.3

        elif abs_dev < self.elite_threshold:
            elasticity_state = "tradable"
            elasticity_score = 0.6

        elif abs_dev < self.extreme_threshold:
            elasticity_state = "elite"
            elasticity_score = 0.85

        else:
            elasticity_state = "extreme"
            elasticity_score = 1.0

        # Mean reversion signal trigger
        reversion_signal = abs_dev >= self.elite_threshold

        return VWAPElasticityResult(
            symbol=symbol,
            mid_price=mid_price,
            vwap=vwap,
            deviation_pct=deviation_pct,
            elasticity_score=elasticity_score,
            elasticity_state=elasticity_state,
            reversion_signal=reversion_signal,
        )

    def to_dict(self, result: VWAPElasticityResult) -> Dict[str, Any]:
        return {
            "symbol": result.symbol,
            "mid_price": result.mid_price,
            "vwap": result.vwap,
            "deviation_pct": result.deviation_pct,
            "elasticity_score": result.elasticity_score,
            "elasticity_state": result.elasticity_state,
            "reversion_signal": result.reversion_signal,
        }