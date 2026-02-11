"""
REA Capital – Risk Governor (Phase 1 Demo Hardening)

Responsibilities:
- Enforce trade limits
- Enforce loss streak limits
- Enforce cooldown after streak
- Enforce max concurrent trades
"""

from datetime import datetime, timedelta


class RiskGovernor:

    MAX_TRADES_PER_DAY = 10
    MAX_CONCURRENT_POSITIONS = 20
    MAX_CONSECUTIVE_LOSSES = 3
    COOLDOWN_HOURS = 8

    def __init__(self):
        self.trade_count_today = 0
        self.consecutive_losses = 0
        self.cooldown_until = None
        self.current_open_positions = 0

    def register_open_positions(self, count: int):
        self.current_open_positions = count

    def can_trade(self):
        now = datetime.utcnow()

        if self.cooldown_until and now < self.cooldown_until:
            return False, f"Cooldown active until {self.cooldown_until}"

        if self.trade_count_today >= self.MAX_TRADES_PER_DAY:
            return False, "Max trades per day reached"

        if self.current_open_positions >= self.MAX_CONCURRENT_POSITIONS:
            return False, "Max concurrent positions reached"

        return True, "OK"

    def record_trade(self):
        self.trade_count_today += 1

    def record_result(self, pnl: float):
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if self.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            self.cooldown_until = datetime.utcnow() + timedelta(hours=self.COOLDOWN_HOURS)
            self.consecutive_losses = 0
