"""
Compounding Engine
==================

Regime-Weighted Controlled Compounding
Capital Strata Systems / REA

Behaviour-aware:
- base_risk_pct is sourced from BehaviourConfig
- drawdown throttle intensity is sourced from BehaviourConfig

Always returns a float.
Never returns tuple.

Default temperament: BALANCED
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from engine.core.behaviour_config import get_behaviour


@dataclass(frozen=True)
class CompoundingProfile:
    """
    BehaviourConfig provides:
    - base_risk_pct
    - drawdown_intensity

    This profile keeps regime logic knobs.
    """
    max_risk_pct: float = 0.0125      # 1.25% hard ceiling
    regime_threshold: float = 0.65
    regime_multiplier: float = 0.5


class CompoundingEngine:

    def __init__(
        self,
        profile: Optional[CompoundingProfile] = None,
        *,
        behaviour: str = "BALANCED",
    ) -> None:
        self.profile = profile or CompoundingProfile()
        self.behaviour = (behaviour or "BALANCED").upper()
        self._cfg = get_behaviour(self.behaviour)

    def compute_dynamic_risk(
        self,
        *,
        equity: float,
        equity_peak: float,
        regime_persistence: float,
    ) -> float:

        p = self.profile
        cfg = self._cfg

        # Defensive type safety
        equity = float(equity)
        equity_peak = float(equity_peak)
        regime_persistence = float(regime_persistence)

        base_risk_pct = float(cfg.base_risk_pct)
        dd_intensity = float(cfg.drawdown_intensity)

        if equity <= 0 or equity_peak <= 0:
            return float(base_risk_pct)

        equity_health = equity / equity_peak
        drawdown = 1.0 - equity_health

        # Drawdown throttle scaling
        raw_factor = 1.0 - (drawdown * dd_intensity)
        drawdown_factor = max(0.25, min(1.0, raw_factor))

        # Weak regime → base risk only
        if regime_persistence < p.regime_threshold:
            return float(base_risk_pct * drawdown_factor)

        # Strong regime → scaled
        scaled = (
            base_risk_pct
            * drawdown_factor
            * (1.0 + regime_persistence * p.regime_multiplier)
        )

        return float(min(float(p.max_risk_pct), scaled))