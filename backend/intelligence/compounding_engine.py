from __future__ import annotations

from typing import Dict


class CompoundingEngine:
    """
    CSS Compounding Engine (Phase FINAL)

    Purpose:
    --------
    Dynamically scale position size based on:
    - Account growth
    - Recent profitability
    - Risk protection

    PCNRASS:
    --------
    - DOES NOT override orchestrator logic
    - ONLY adjusts position size multiplier
    """

    def __init__(self) -> None:
        self.base_risk = 1.0  # baseline multiplier

    def compute_multiplier(
        self,
        account_balance: float,
        starting_balance: float,
        recent_pnl: float,
    ) -> float:
        """
        Returns safe compounding multiplier
        """

        if starting_balance <= 0:
            return 1.0

        growth_ratio = account_balance / starting_balance

        # --- Growth scaling ---
        if growth_ratio >= 2.0:
            growth_boost = 1.5
        elif growth_ratio >= 1.5:
            growth_boost = 1.3
        elif growth_ratio >= 1.2:
            growth_boost = 1.15
        else:
            growth_boost = 1.0

        # --- Recent performance scaling ---
        if recent_pnl > 0:
            pnl_boost = 1.1
        elif recent_pnl < 0:
            pnl_boost = 0.9
        else:
            pnl_boost = 1.0

        multiplier = growth_boost * pnl_boost

        # --- HARD SAFETY CAPS ---
        multiplier = max(0.5, min(multiplier, 2.0))

        return multiplier