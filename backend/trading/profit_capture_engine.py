from __future__ import annotations

from typing import Dict


class ProfitCaptureEngine:
    """
    CSS Profit Capture Engine

    Exit logic:
    - stop loss
    - take profit
    - simple profit lock once trade moves sufficiently in favor
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

    def evaluate(self, entry_price: float, current_price: float) -> Dict:
        if entry_price <= 0:
            return {"action": "HOLD", "pnl_pct": 0.0, "reason": "invalid entry"}

        change = (current_price - entry_price) / entry_price

        if change <= -self.stop_loss:
            return {
                "action": "STOP_LOSS",
                "pnl_pct": change,
                "reason": "hard stop loss hit",
            }

        if change >= self.take_profit:
            return {
                "action": "TAKE_PROFIT",
                "pnl_pct": change,
                "reason": "full take profit hit",
            }

        if change >= self.trail_trigger:
            if change <= self.locked_profit:
                return {
                    "action": "TAKE_PROFIT",
                    "pnl_pct": change,
                    "reason": "profit lock triggered",
                }

        return {
            "action": "HOLD",
            "pnl_pct": change,
            "reason": "position within active range",
        }