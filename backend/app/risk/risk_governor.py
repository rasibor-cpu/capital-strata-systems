# LEGACY RISK GOVERNOR - NON-CANONICAL.
# ARP-011 quarantine marker: the canonical execution RiskGovernor is
# engine/risk/risk_governor.py. This nested backend app copy is retained for
# historical compatibility and must not be treated as the active execution risk
# authority.

"""
Risk Governor – REA Capital
Hard execution controls
"""

from dataclasses import dataclass


@dataclass
class RiskState:
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_pnl: float = 0.0


class RiskGovernor:

    MAX_TRADES_PER_DAY = 10
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_DAILY_DRAWDOWN = -0.02  # -2% equity cap (adjust later)

    def __init__(self):
        self.state = RiskState()

    def can_trade(self, account_balance: float) -> bool:

        if self.state.trades_today >= self.MAX_TRADES_PER_DAY:
            print("BLOCK: Max trades per day reached.")
            return False

        if self.state.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            print("BLOCK: Consecutive loss limit reached.")
            return False

        if account_balance <= 0:
            print("BLOCK: Invalid account balance.")
            return False

        return True

    def record_trade(self, pnl: float):

        self.state.trades_today += 1
        self.state.daily_pnl += pnl

        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
