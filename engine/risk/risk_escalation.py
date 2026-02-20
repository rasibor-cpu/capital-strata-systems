"""
RiskEscalation – Controlled Profit Acceleration Layer
Capital Strata Systems (CSS)

Purpose:
- Increase capital deployment only when system proves edge
- Anti-martingale scaling (increase on strength, compress on weakness)
- Hard cap enforcement
- Equity-aware dynamic scaling

This module NEVER overrides:
- Hard drawdown breaker
- RiskGovernor validation
- Weekly loss clamps
It only scales notional upward under controlled conditions.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict


# ============================================================
# CONFIGURATION
# ============================================================

BASE_NOTIONAL = 10_000.0
MAX_MULTIPLIER = 2.0          # Never exceed 2x base
MIN_MULTIPLIER = 0.5          # Compression floor
ESCALATION_STEP = 0.05        # +5% increments
DRAWDOWN_COMPRESSION = 0.10   # If drawdown > 10%, compress


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class EscalationState:
    multiplier: float = 1.0
    last_equity_peak: float = 0.0


# ============================================================
# CORE ENGINE
# ============================================================

class RiskEscalation:

    def __init__(self) -> None:
        self.state = EscalationState(multiplier=1.0)

    # --------------------------------------------------------

    def adjust_multiplier(
        self,
        current_equity: float,
        peak_equity: float,
        total_realized: float,
    ) -> float:
        """
        Anti-martingale logic:

        - If new equity high → gently increase multiplier
        - If in drawdown beyond threshold → compress exposure
        - Always remain within bounds
        """

        drawdown = 0.0
        if peak_equity > 0:
            drawdown = (peak_equity - current_equity) / peak_equity

        # PROFIT EXPANSION
        if current_equity > self.state.last_equity_peak:
            self.state.last_equity_peak = current_equity
            self.state.multiplier += ESCALATION_STEP

        # DRAWDOWN COMPRESSION
        if drawdown > DRAWDOWN_COMPRESSION:
            self.state.multiplier -= ESCALATION_STEP * 2

        # BOUNDARIES
        self.state.multiplier = max(MIN_MULTIPLIER, self.state.multiplier)
        self.state.multiplier = min(MAX_MULTIPLIER, self.state.multiplier)

        return self.state.multiplier

    # --------------------------------------------------------

    def scaled_notional(
        self,
        base_notional: float,
        current_equity: float,
        peak_equity: float,
        total_realized: float,
    ) -> float:

        multiplier = self.adjust_multiplier(
            current_equity=current_equity,
            peak_equity=peak_equity,
            total_realized=total_realized,
        )

        return base_notional * multiplier
