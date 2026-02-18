"""
Compounding Controller – Institutional Tier Logic
=================================================

Stateful strategic controller layered above CompoundingEngine.

Responsibilities:
- Track rolling trade performance
- Enforce tier escalation rules
- Reset tiers on drawdown breach
- Delegate risk math to CompoundingEngine

Capital Strata Systems
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from engine.capital.compounding_engine import CompoundingEngine


# ============================================================
# Tier Profile
# ============================================================

@dataclass(frozen=True)
class TierProfile:
    base_risk: float = 0.005
    tier_1: float = 0.007
    tier_2: float = 0.009
    tier_3: float = 0.011
    cap: float = 0.0125

    drawdown_reset_threshold: float = 0.04  # 4%
    momentum_window: int = 5
    consecutive_win_trigger: int = 3
    regime_threshold: float = 0.70


# ============================================================
# Controller
# ============================================================

class CompoundingController:

    def __init__(self, profile: Optional[TierProfile] = None) -> None:
        self.profile = profile or TierProfile()
        self.engine = CompoundingEngine()

        self.trade_history: List[float] = []
        self.current_tier = 0
        self.initial_equity: Optional[float] = None

    # --------------------------------------------------------
    # Trade Recording
    # --------------------------------------------------------

    def record_trade(self, pnl: float) -> None:
        self.trade_history.append(pnl)

        if len(self.trade_history) > self.profile.momentum_window:
            self.trade_history.pop(0)

    # --------------------------------------------------------
    # Tier Logic
    # --------------------------------------------------------

    def _check_drawdown_reset(self, equity: float, equity_peak: float) -> bool:
        if equity_peak <= 0:
            return False

        dd = (equity_peak - equity) / equity_peak
        return dd >= self.profile.drawdown_reset_threshold

    def _momentum_positive(self) -> bool:
        if len(self.trade_history) < self.profile.momentum_window:
            return False

        return sum(self.trade_history) > 0

    def _consecutive_wins(self) -> int:
        count = 0
        for pnl in reversed(self.trade_history):
            if pnl > 0:
                count += 1
            else:
                break
        return count

    # --------------------------------------------------------
    # Public Interface
    # --------------------------------------------------------

    def compute_risk(
        self,
        *,
        equity: float,
        equity_peak: float,
        regime_persistence: float,
    ) -> Tuple[float, bool]:

        if self.initial_equity is None:
            self.initial_equity = equity

        # Reset tier if drawdown breached
        if self._check_drawdown_reset(equity, equity_peak):
            self.current_tier = 0

        # Regime condition
        regime_ok = regime_persistence >= self.profile.regime_threshold

        # Momentum condition
        momentum_ok = self._momentum_positive()
        streak_ok = self._consecutive_wins() >= self.profile.consecutive_win_trigger

        # Tier escalation logic
        if regime_ok and (momentum_ok or streak_ok):

            if equity >= self.initial_equity * 1.08:
                self.current_tier = 3
            elif len(self.trade_history) >= 10 and momentum_ok:
                self.current_tier = 2
            else:
                self.current_tier = 1

        # Map tier to risk
        if self.current_tier == 0:
            risk = self.profile.base_risk
        elif self.current_tier == 1:
            risk = self.profile.tier_1
        elif self.current_tier == 2:
            risk = self.profile.tier_2
        else:
            risk = self.profile.tier_3

        risk = min(risk, self.profile.cap)

        comp_applied = self.current_tier > 0

        return risk, comp_applied
