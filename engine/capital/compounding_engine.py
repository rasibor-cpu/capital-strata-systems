"""
Compounding Engine
==================

Regime-Weighted Controlled Compounding
Capital Strata Systems / REA

Always returns a float.
Never returns tuple.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CompoundingProfile:
    base_risk_pct: float = 0.005      # 0.5%
    max_risk_pct: float = 0.0125      # 1.25%
    regime_threshold: float = 0.65
    regime_multiplier: float = 0.5


class CompoundingEngine:

    def __init__(self, profile: Optional[CompoundingProfile] = None) -> None:
        self.profile = profile or CompoundingProfile()

    def compute_dynamic_risk(
        self,
        *,
        equity: float,
        equity_peak: float,
        regime_persistence: float,
    ) -> float:

        p = self.profile

        # Defensive type safety
        equity = float(equity)
        equity_peak = float(equity_peak)
        regime_persistence = float(regime_persistence)

        if equity <= 0 or equity_peak <= 0:
            return float(p.base_risk_pct)

        equity_health = equity / equity_peak
        drawdown = 1.0 - equity_health

        drawdown_factor = max(0.5, 1.0 - drawdown)

        # Weak regime → base risk only
        if regime_persistence < p.regime_threshold:
            return float(p.base_risk_pct * drawdown_factor)

        # Strong regime → scaled
        scaled = (
            p.base_risk_pct
            * drawdown_factor
            * (1.0 + regime_persistence * p.regime_multiplier)
        )

        return float(min(p.max_risk_pct, scaled))
