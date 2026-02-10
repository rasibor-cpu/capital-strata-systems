from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional


# ============================================================
# Risk Configuration
# ============================================================

@dataclass
class RiskConfig:
    max_trades_per_day: int
    max_concurrent_positions: int
    max_daily_drawdown_pct: float
    max_consecutive_losses: int
    starting_equity: float
    max_peak_drawdown_pct: float = 0.20   # 20% peak-to-trough cap
    cooldown_hours: int = 12


# ============================================================
# Risk State
# ============================================================

@dataclass
class RiskState:
    trades_today: int = 0
    open_positions: int = 0
    daily_pnl: float = 0.0
    consecutive_losses: int = 0

    # Cooldown
    cooldown_active: bool = False
    cooldown_until_utc: Optional[str] = None

    # High watermark tracking
    equity_peak: float = 0.0


# ============================================================
# Risk Governor
# ============================================================

class RiskGovernor:

    def __init__(self, config: RiskConfig):
        self.config = config
        self.state = RiskState(equity_peak=config.starting_equity)

    # --------------------------------------------------------
    # Utility
    # --------------------------------------------------------

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _cooldown_expired(self) -> bool:
        if not self.state.cooldown_active:
            return True
        if not self.state.cooldown_until_utc:
            return True
        until = datetime.fromisoformat(self.state.cooldown_until_utc)
        return self._utc_now() >= until

    def _activate_cooldown(self):
        if not self.state.cooldown_active:
            until = self._utc_now() + timedelta(hours=self.config.cooldown_hours)
            self.state.cooldown_active = True
            self.state.cooldown_until_utc = until.isoformat()

    def _clear_cooldown(self):
        self.state.cooldown_active = False
        self.state.cooldown_until_utc = None
        self.state.consecutive_losses = 0

    # --------------------------------------------------------
    # Equity / Peak Tracking
    # --------------------------------------------------------

    def update_equity_peak(self, current_equity: float):
        if current_equity > self.state.equity_peak:
            self.state.equity_peak = current_equity

    def _peak_drawdown_breached(self, current_equity: float) -> Tuple[bool, float]:
        peak = self.state.equity_peak
        if peak <= 0:
            return False, 0.0

        drawdown_pct = (current_equity - peak) / peak
        if drawdown_pct <= -self.config.max_peak_drawdown_pct:
            return True, drawdown_pct
        return False, drawdown_pct

    # --------------------------------------------------------
    # Core Evaluation
    # --------------------------------------------------------

    def evaluate(self, current_equity: float = None) -> Tuple[str, str]:

        # 1️⃣ Peak drawdown check (highest priority)
        if current_equity is not None:
            breached, dd_pct = self._peak_drawdown_breached(current_equity)
            if breached:
                return (
                    "BLOCKED",
                    f"MAX_PEAK_DRAWDOWN_EXCEEDED: drawdown_pct={round(dd_pct,4)} <= limit={-self.config.max_peak_drawdown_pct}"
                )

        # 2️⃣ Cooldown enforcement
        if self.state.cooldown_active:
            if not self._cooldown_expired():
                return (
                    "BLOCKED",
                    f"COOLDOWN_ACTIVE: until={self.state.cooldown_until_utc}"
                )
            else:
                self._clear_cooldown()

        # 3️⃣ Trades per day
        if self.state.trades_today >= self.config.max_trades_per_day:
            return (
                "BLOCKED",
                f"MAX_TRADES_PER_DAY_EXCEEDED: trades_today={self.state.trades_today} >= limit={self.config.max_trades_per_day}"
            )

        # 4️⃣ Consecutive losses
        if self.state.consecutive_losses >= self.config.max_consecutive_losses:
            self._activate_cooldown()
            return (
                "BLOCKED",
                f"MAX_CONSECUTIVE_LOSSES_EXCEEDED: consecutive_losses={self.state.consecutive_losses} >= limit={self.config.max_consecutive_losses}"
            )

        # 5️⃣ Daily drawdown
        max_drawdown_value = -self.config.starting_equity * self.config.max_daily_drawdown_pct
        if self.state.daily_pnl <= max_drawdown_value:
            return (
                "BLOCKED",
                f"MAX_DAILY_DRAWDOWN_EXCEEDED: daily_pnl={self.state.daily_pnl} <= limit={max_drawdown_value}"
            )

        return ("APPROVED", "Risk checks passed")

    # --------------------------------------------------------
    # State Mutation
    # --------------------------------------------------------

    def record_trade(self, pnl: float, current_equity: float):
        self.state.trades_today += 1
        self.state.daily_pnl += pnl

        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0

        # Update peak tracking
        self.update_equity_peak(current_equity)

    def record_open_position(self):
        self.state.open_positions += 1

    def record_close_position(self):
        if self.state.open_positions > 0:
            self.state.open_positions -= 1

    def reset_day(self):
        self.state = RiskState(equity_peak=self.state.equity_peak)
