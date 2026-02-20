"""
CostEngine – Moderate Realism (Retail FX) Market Friction
Capital Strata Systems (CSS)

Applies:
- Spread cost (pair-specific bps, retail-realistic)
- Slippage (mild, asymmetric: losers punished more than winners)
- Commission (flat per trade)

This module is intentionally simple, deterministic, and simulation-safe.
"""

from __future__ import annotations

from typing import Dict
import random


class CostEngine:
    # Retail-realistic spread bps per pair
    SPREAD_BPS: Dict[str, float] = {
        "EUR_USD": 2.5,
        "GBP_USD": 3.5,
        "USD_JPY": 2.0,
        "AUD_USD": 3.0,
        "USD_CHF": 3.0,
    }

    # Slippage max (bps) — asymmetric
    SLIPPAGE_BPS_WIN = 1.0
    SLIPPAGE_BPS_LOSS = 3.0

    # Flat commission per trade (USD)
    COMMISSION_PER_TRADE = 3.0

    def __init__(self, deterministic: bool = True) -> None:
        self.deterministic = deterministic
        if deterministic:
            random.seed(42)

    def apply(
        self,
        *,
        instrument: str,
        notional: float,
        raw_pnl: float,
    ) -> float:
        """
        Return pnl AFTER execution costs.
        """

        spread_bps = float(self.SPREAD_BPS.get(instrument, 3.0))

        # Spread cost proportional to notional
        spread_cost = (spread_bps / 10000.0) * float(notional)

        # Slippage proportional to notional, asymmetric to trade outcome
        slip_bps = self.SLIPPAGE_BPS_WIN if raw_pnl >= 0 else self.SLIPPAGE_BPS_LOSS
        slip = random.uniform(-slip_bps, slip_bps) / 10000.0
        slippage_cost = abs(slip * float(notional))

        total_cost = spread_cost + slippage_cost + float(self.COMMISSION_PER_TRADE)

        return float(raw_pnl) - float(total_cost)
