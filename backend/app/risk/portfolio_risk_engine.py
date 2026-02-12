"""
Capital Strata Systems
Portfolio Risk Engine (Standalone)

Purpose:
- Aggregate cross-asset risk into ONE portfolio view (FX + Futures + others later)
- Compute total portfolio risk amount and allocation % vs equity
- MUST NOT import RiskGovernor (avoid circular imports)

This module is intentionally "dumb + pure":
- No broker calls
- No engine state mutations
- No imports from engine.*
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    total_risk: float
    allocation_pct: float
    components: Dict[str, float]


class PortfolioRiskEngine:
    """
    Simple portfolio risk aggregator.
    All inputs are absolute "risk money" amounts (same base currency).
    Example:
      fx_risk = 120.0      # dollars at risk on next FX trade
      futures_risk = 500.0 # dollars at risk across open futures
    """

    def calculate_total_risk(
        self,
        *,
        fx_risk: float = 0.0,
        futures_risk: float = 0.0,
        equities_risk: float = 0.0,
        crypto_risk: float = 0.0,
        rates_risk: float = 0.0,
    ) -> float:
        total = (
            float(fx_risk)
            + float(futures_risk)
            + float(equities_risk)
            + float(crypto_risk)
            + float(rates_risk)
        )
        return max(total, 0.0)

    def snapshot(
        self,
        *,
        equity: float,
        fx_risk: float = 0.0,
        futures_risk: float = 0.0,
        equities_risk: float = 0.0,
        crypto_risk: float = 0.0,
        rates_risk: float = 0.0,
    ) -> PortfolioRiskSnapshot:
        eq = float(equity)
        total = self.calculate_total_risk(
            fx_risk=fx_risk,
            futures_risk=futures_risk,
            equities_risk=equities_risk,
            crypto_risk=crypto_risk,
            rates_risk=rates_risk,
        )
        allocation = (total / eq) if eq > 0 else 0.0

        return PortfolioRiskSnapshot(
            total_risk=round(total, 6),
            allocation_pct=round(allocation, 6),
            components={
                "fx_risk": round(float(fx_risk), 6),
                "futures_risk": round(float(futures_risk), 6),
                "equities_risk": round(float(equities_risk), 6),
                "crypto_risk": round(float(crypto_risk), 6),
                "rates_risk": round(float(rates_risk), 6),
            },
        )

    def to_dict(self, snap: PortfolioRiskSnapshot) -> Dict[str, Any]:
        return {
            "total_risk": snap.total_risk,
            "allocation_pct": snap.allocation_pct,
            "components": dict(snap.components),
        }
