"""
Compounding Engine
==================

Regime-Weighted Controlled Compounding
Capital Strata Systems / REA

Scales risk only when:
- Equity is healthy
- Regime persistence is strong
- Drawdown is controlled

Governor remains final authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CompoundingProfile:
    base_risk_pct: float = 0.005      # 0.5%
    max_risk_pct: float = 0.0125      # 1.25%
    regime_threshold: float = 0.65
    regime_multiplier: float = 0.5    # strength of scaling effect


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

        if equity <= 0 or equity_peak <= 0:
            return p.base_risk_pct

        # ---- Equity Health ----
        equity_health = equity / equity_peak
        drawdown = 1.0 - equity_health

        drawdown_factor = max(0.5, 1.0 - drawdown)

        # ---- Regime Check ----
        if regime_persistence < p.regime_threshold:
            return p.base_risk_pct * drawdown_factor

        # ---- Scale Risk ----
        scaled = (
            p.base_risk_pct
            * drawdown_factor
            * (1.0 + regime_persistence * p.regime_multiplier)
        )

        return min(p.max_risk_pct, scaled)
