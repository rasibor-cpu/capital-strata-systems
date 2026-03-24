from __future__ import annotations

from typing import Dict


class ProfitCaptureEngine:
    """
    CSS Profit Capture Engine (Upgraded)

    Features:
    - Hard stop loss
    - Hard take profit (safety cap only)
    - Dynamic trailing logic
    - Profit lock after favorable move
    - Lets winners run
    """

    def __init__(
        self,
        take_profit_bps: float,
        stop_loss_bps: float,
        trail_trigger_bps: float = 40.0,
        locked_profit_bps: float = 15.0,
    ):
        self.take_profit = take_profit_bps / 10000.0
        self.stop_loss = stop_loss_bps / 10000.0
        self.trail_trigger = trail_trigger_bps / 10000.0
        self.locked_profit = locked_profit_bps / 10000.0

    def evaluate(
        self,
        entry_price: float,
        current_price: float,
        peak_price: float,
    ) -> Dict:

        if entry_price <= 0:
            return {"action": "HOLD", "pnl_pct": 0.0, "reason": "invalid entry"}

        change = (current_price - entry_price) / entry_price
        peak_change = (peak_price - entry_price) / entry_price

        # -------------------------
        # HARD STOP LOSS
        # -------------------------
        if change <= -self.stop_loss:
            return {
                "action": "STOP_LOSS",
                "pnl_pct": change,
                "reason": "hard stop loss hit",
            }

        # -------------------------
        # HARD TAKE PROFIT (RARE)
        # -------------------------
        if change >= self.take_profit:
            return {
                "action": "TAKE_PROFIT",
                "pnl_pct": change,
                "reason": "hard take profit cap",
            }

        # -------------------------
        # TRAILING LOGIC
        # -------------------------
        if peak_change >= self.trail_trigger:

            lock_level = entry_price * (1 + self.locked_profit)

            # if price falls below locked level → exit
            if current_price < lock_level:
                return {
                    "action": "EXIT_LOCK_PROFIT",
                    "pnl_pct": change,
                    "reason": "trailing profit lock triggered",
                }

            # still trending → hold
            return {
                "action": "HOLD",
                "pnl_pct": change,
                "reason": "winner running with trailing protection",
            }

        # -------------------------
        # DEFAULT HOLD
        # -------------------------
        return {
            "action": "HOLD",
            "pnl_pct": change,
            "reason": "within normal range",
        }