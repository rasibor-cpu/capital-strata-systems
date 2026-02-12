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
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    total_risk: float
    allocation_pct: float
    components: Dict[str, float]


class PortfolioRiskEngine:
    """
    Simple portfolio risk aggregator.

    Convention:
    - All inputs are absolute "risk money" amounts (same base currency).
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

    # ==========================================================
    # Compatibility method (called by RiskGovernor)
    # ==========================================================
    def evaluate_new_trade(
        self,
        *,
        instrument: str,
        equity: float,
        state: Optional[Dict[str, Any]] = None,
        # RiskGovernor may pass either name; we accept both.
        new_trade_risk: Optional[float] = None,
        trade_risk: Optional[float] = None,
        # Optional cap passed by governor
        max_total_pct: Optional[float] = None,
        # Optional explicit open-risk inputs (else we fallback to state keys)
        open_futures_risk: float = 0.0,
        open_fx_risk: float = 0.0,
        open_equities_risk: float = 0.0,
        open_crypto_risk: float = 0.0,
        open_rates_risk: float = 0.0,
        **_kwargs: Any,  # ignore any future governor params safely
    ) -> Dict[str, Any]:
        """
        Compute what portfolio exposure would be IF we add a new trade.

        Returns a dict with:
        - status: APPROVED or BLOCKED (if max_total_pct provided and exceeded)
        - allocation_pct, total_risk, components
        - proposed_trade_risk
        """

        s = state or {}

        proposed = new_trade_risk if new_trade_risk is not None else trade_risk
        proposed_trade_risk = float(proposed or 0.0)

        # Fallback to state values if explicit args not provided
        futures_risk = float(open_futures_risk) if open_futures_risk else float(s.get("open_futures_risk") or 0.0)
        fx_existing = float(open_fx_risk) if open_fx_risk else float(s.get("open_fx_risk") or 0.0)
        equities_risk = float(open_equities_risk) if open_equities_risk else float(s.get("open_equities_risk") or 0.0)
        crypto_risk = float(open_crypto_risk) if open_crypto_risk else float(s.get("open_crypto_risk") or 0.0)
        rates_risk = float(open_rates_risk) if open_rates_risk else float(s.get("open_rates_risk") or 0.0)

        # Proposed trade treated as FX risk for now
        proposed_fx_total = fx_existing + proposed_trade_risk

        snap = self.snapshot(
            equity=float(equity),
            fx_risk=proposed_fx_total,
            futures_risk=futures_risk,
            equities_risk=equities_risk,
            crypto_risk=crypto_risk,
            rates_risk=rates_risk,
        )

        out = self.to_dict(snap)

        status = "APPROVED"
        reason = "portfolio_risk_ok"
        if max_total_pct is not None:
            cap = float(max_total_pct)
            if out["allocation_pct"] > cap:
                status = "BLOCKED"
                reason = f"portfolio_allocation {out['allocation_pct']:.2%} > cap {cap:.2%}"

        out.update(
            {
                "status": status,
                "reason": reason,
                "instrument": str(instrument),
                "proposed_trade_risk": round(proposed_trade_risk, 6),
                "max_total_pct": round(float(max_total_pct), 6) if max_total_pct is not None else None,
            }
        )
        return out
