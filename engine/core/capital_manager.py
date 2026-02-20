"""
CapitalManager – Global Capital Throttle
Capital Strata Systems (CSS)

Institutional capital discipline layer.

Purpose:
- Protect global equity
- Reduce exposure during drawdowns
- Allow controlled scaling during strength
- Prevent death-spiral behavior

This sits ABOVE instrument-level clamps.
"""

from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# CONFIGURATION
# ============================================================

GLOBAL_SOFT_DD_START = 0.05     # 5% drawdown → begin soft scaling
GLOBAL_HARD_DD_LIMIT = 0.15     # 15% drawdown → freeze new exposure
MAX_CAPITAL_MULTIPLIER = 1.25   # allow 25% scale-up at strength
MIN_CAPITAL_MULTIPLIER = 0.25   # never drop below 25% exposure


# ============================================================
# STATE STRUCTURE
# ============================================================

@dataclass
class CapitalState:
    drawdown_pct: float
    capital_multiplier: float
    hard_stop: bool


# ============================================================
# CORE MANAGER
# ============================================================

class CapitalManager:

    def __init__(self):
        self.peak_equity = None

    # --------------------------------------------------------

    def update(self, current_equity: float) -> CapitalState:

        if self.peak_equity is None:
            self.peak_equity = current_equity

        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        drawdown = 0.0
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - current_equity) / self.peak_equity

        # Hard stop condition
        if drawdown >= GLOBAL_HARD_DD_LIMIT:
            return CapitalState(
                drawdown_pct=drawdown,
                capital_multiplier=0.0,
                hard_stop=True,
            )

        # Soft scaling zone
        if drawdown >= GLOBAL_SOFT_DD_START:
            # Linear compression between soft start and hard stop
            compression_range = GLOBAL_HARD_DD_LIMIT - GLOBAL_SOFT_DD_START
            excess = drawdown - GLOBAL_SOFT_DD_START
            scale = 1.0 - (excess / compression_range)
            scale = max(scale, MIN_CAPITAL_MULTIPLIER)

            return CapitalState(
                drawdown_pct=drawdown,
                capital_multiplier=scale,
                hard_stop=False,
            )

        # Growth zone (scale modestly when strong)
        strength = 1.0 - drawdown
        scale = min(1.0 + (strength * 0.10), MAX_CAPITAL_MULTIPLIER)

        return CapitalState(
            drawdown_pct=drawdown,
            capital_multiplier=scale,
            hard_stop=False,
        )
