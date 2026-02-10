from __future__ import annotations

from datetime import datetime, timezone


class Simulator:

    def __init__(self, starting_equity: float = 100000.0):
        self.starting_equity = starting_equity
        self.equity = starting_equity

        self.position = None
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0

        self.cooldown_active = False
        self.cooldown_until = None

        self.equity_peak = starting_equity

    # --------------------------------------------------

    def reset(self):
        self.__init__(self.starting_equity)

    # --------------------------------------------------

    def inject_win(self, pnl: float):
        self.equity += pnl
        self.daily_pnl += pnl
        self.trades_today += 1
        self.consecutive_losses = 0

        if self.equity > self.equity_peak:
            self.equity_peak = self.equity

        return pnl

    # --------------------------------------------------

    def inject_loss(self, pnl: float):
        self.equity += pnl
        self.daily_pnl += pnl
        self.trades_today += 1
        self.consecutive_losses += 1

        return pnl

    # --------------------------------------------------

    def open_position(self, side: str, entry_price: float, size: float):
        self.position = {
            "side": side,
            "entry_price": entry_price,
            "size": size,
            "entry_tick_id": 0,
            "stop_distance": 1.0,
        }
        return self.position

    # --------------------------------------------------

    def close_position(self, pnl: float):
        self.equity += pnl
        self.daily_pnl += pnl
        self.trades_today += 1

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if self.equity > self.equity_peak:
            self.equity_peak = self.equity

        self.position = None
        return pnl

    # --------------------------------------------------

    def risk_state(self):
        return {
            "trades_today": self.trades_today,
            "open_positions": 1 if self.position else 0,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_active": self.cooldown_active,
            "cooldown_until_utc": (
                self.cooldown_until.isoformat()
                if self.cooldown_until
                else None
            ),
            "equity_peak": self.equity_peak,
        }

