"""
Hard loss kill-switch.
Blocks NEW trades when loss limits are breached.
Allows only reduce / close actions.
"""

from datetime import datetime, timezone, date
from dataclasses import dataclass

@dataclass
class LossState:
    trading_day: date
    trading_week: int
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    daily_locked: bool = False
    weekly_locked: bool = False


class LossKillSwitch:
    def __init__(
        self,
        max_daily_loss: float,
        max_weekly_loss: float,
    ):
        self.max_daily_loss = abs(max_daily_loss)
        self.max_weekly_loss = abs(max_weekly_loss)
        self.state = None

    def _current_state(self):
        now = datetime.now(timezone.utc)
        iso_year, iso_week, _ = now.isocalendar()
        return now.date(), iso_week

    def reset_if_new_period(self):
        today, week = self._current_state()

        if self.state is None:
            self.state = LossState(today, week)
            return

        if today != self.state.trading_day:
            self.state.trading_day = today
            self.state.daily_pnl = 0.0
            self.state.daily_locked = False

        if week != self.state.trading_week:
            self.state.trading_week = week
            self.state.weekly_pnl = 0.0
            self.state.weekly_locked = False

    def update_pnl(self, realized_pnl: float):
        self.reset_if_new_period()

        self.state.daily_pnl += realized_pnl
        self.state.weekly_pnl += realized_pnl

        if self.state.daily_pnl <= -self.max_daily_loss:
            self.state.daily_locked = True

        if self.state.weekly_pnl <= -self.max_weekly_loss:
            self.state.weekly_locked = True

    def allow_new_trade(self) -> bool:
        self.reset_if_new_period()
        return not (self.state.daily_locked or self.state.weekly_locked)

    def status(self) -> dict:
        self.reset_if_new_period()
        return {
            "daily_pnl": self.state.daily_pnl,
            "weekly_pnl": self.state.weekly_pnl,
            "daily_locked": self.state.daily_locked,
            "weekly_locked": self.state.weekly_locked,
        }


if __name__ == "__main__":
    # smoke test
    ks = LossKillSwitch(max_daily_loss=500, max_weekly_loss=1500)
    ks.update_pnl(-200)
    ks.update_pnl(-350)
    print("ALLOW NEW:", ks.allow_new_trade())
    print("STATUS:", ks.status())
