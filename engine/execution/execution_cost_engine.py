"""
ExecutionCostEngine – Institutional Friction Model
Capital Strata Systems (CSS)

Authoritative execution boundary friction layer.

Applies:
- Spread (bps per instrument)
- Slippage (deterministic or mild stochastic)
- Commission (flat per trade)

Design Principles:
- Friction applied AFTER signal approval
- Pure function behavior (no equity mutation here)
- Deterministic mode available for testing
"""

from __future__ import annotations

from typing import Dict
import random


class ExecutionCostEngine:

    def __init__(self, deterministic: bool = True) -> None:
        """
        deterministic=True:
            slippage fixed at midpoint
        deterministic=False:
            slippage sampled within band
        """
        self.deterministic = deterministic

        # Spread in basis points (round-trip approximation)
        self.spread_bps: Dict[str, float] = {
            "EUR_USD": 1.2,
            "GBP_USD": 1.5,
            "USD_JPY": 1.3,
            "AUD_USD": 1.6,
            "USD_CHF": 1.4,
        }

        # Slippage band in basis points
        self.slippage_bps_band = 0.8

        # Flat commission per trade
        self.commission_per_trade = 5.0

    # --------------------------------------------------

    def _compute_spread_cost(self, instrument: str, notional: float) -> float:
        bps = self.spread_bps.get(instrument, 1.5)
        return notional * (bps / 10000.0)

    # --------------------------------------------------

    def _compute_slippage_cost(self, notional: float) -> float:
        if self.deterministic:
            bps = self.slippage_bps_band / 2.0
        else:
            bps = random.uniform(0.0, self.slippage_bps_band)

        return notional * (bps / 10000.0)

    # --------------------------------------------------

    def apply_costs(
        self,
        *,
        instrument: str,
        notional: float,
        raw_pnl: float,
    ) -> float:
        """
        Returns cost-adjusted realized pnl.
        """

        spread_cost = self._compute_spread_cost(instrument, notional)
        slippage_cost = self._compute_slippage_cost(notional)
        commission_cost = self.commission_per_trade

        total_cost = spread_cost + slippage_cost + commission_cost

        return raw_pnl - total_cost
