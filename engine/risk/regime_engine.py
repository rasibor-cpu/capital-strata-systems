"""
Capital Strata Systems
Regime Classification Engine

Pure classification.
No broker calls.
No RiskGovernor imports.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: str
    volatility_ratio: float
    risk_multiplier: float


class RegimeEngine:

    def classify(self, volatility_ratio: float) -> RegimeSnapshot:

        vr = float(volatility_ratio)

        if vr > 1.5:
            return RegimeSnapshot(
                regime="CRISIS",
                volatility_ratio=vr,
                risk_multiplier=0.5,
            )

        elif vr > 1.0:
            return RegimeSnapshot(
                regime="UNSTABLE",
                volatility_ratio=vr,
                risk_multiplier=0.75,
            )

        return RegimeSnapshot(
            regime="CALM",
            volatility_ratio=vr,
            risk_multiplier=1.0,
        )
