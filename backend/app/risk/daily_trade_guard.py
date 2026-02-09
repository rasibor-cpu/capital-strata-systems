"""
Daily Trade Guard – REA Capital Trading Engine
----------------------------------------------

Purpose:
- Enforce maximum trades per day.
- Reset automatically at UTC date change.
- Provide structured status response.
- Fail-safe: missing state initializes safely.

Policy:
- max_trades = 10 per calendar UTC day
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class DailyTradeState:
    trades_today: int = 0
    current_day: str = ""


class DailyTradeGuard:
    def __init__(self, max_trades: int = 10):
        self.max_trades = max_trades
        self.state = DailyTradeState()
        self._initialize_day()

    # -------------------------------------------------------
    # internal helpers
    # -------------------------------------------------------

    def _today_utc(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _initialize_day(self):
        today = self._today_utc()
        if not self.state.current_day:
            self.state.current_day = today
            self.state.trades_today = 0

    def _rollover_if_new_day(self):
        today = self._today_utc()
        if self.state.current_day != today:
            self.state.current_day = today
            self.state.trades_today = 0

    # -------------------------------------------------------
    # public interface
    # -------------------------------------------------------

    def can_trade(self) -> bool:
        self._rollover_if_new_day()
        return self.state.trades_today < self.max_trades

    def record_trade(self):
        self._rollover_if_new_day()
        self.state.trades_today += 1

    def status(self) -> dict:
        self._rollover_if_new_day()
        return {
            "current_day": self.state.current_day,
            "trades_today": self.state.trades_today,
            "max_trades": self.max_trades,
            "remaining": max(self.max_trades - self.state.trades_today, 0),
            "allowed": self.state.trades_today < self.max_trades,
        }
