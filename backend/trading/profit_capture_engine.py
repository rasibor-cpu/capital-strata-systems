from __future__ import annotations

from typing import Dict


class ProfitCaptureEngine:

    def __init__(self, take_profit_bps: float, stop_loss_bps: float):

        self.take_profit = take_profit_bps / 10000
        self.stop_loss = stop_loss_bps / 10000

    def evaluate(self, entry_price: float, current_price: float) -> Dict:

        if entry_price <= 0:
            return {"action": "HOLD"}

        change = (current_price - entry_price) / entry_price

        if change >= self.take_profit:
            return {"action": "TAKE_PROFIT", "pnl_pct": change}

        if change <= -self.stop_loss:
            return {"action": "STOP_LOSS", "pnl_pct": change}

        return {"action": "HOLD", "pnl_pct": change}