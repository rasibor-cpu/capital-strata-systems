"""
DrawdownScaler
==============

Institutional drawdown-adaptive risk compression layer.

Design:
- Independent of RiskGovernor
- Pure function of equity + equity_peak
- No state mutation
- Hard 20% capital kill-switch

Capital Strata Systems
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DrawdownResult:
    drawdown_pct: float
    multiplier: float
    hard_stop: bool


class DrawdownScaler:
    """
    Institutional risk compression model.

    Scaling model:
        0–5%     -> 1.00
        5–10%    -> 0.75
        10–15%   -> 0.50
        15–20%   -> 0.25
        >=20%    -> HARD STOP
    """

    HARD_LIMIT = 0.20

    def evaluate(
        self,
        *,
        equity: Optional[float],
        equity_peak: Optional[float],
    ) -> DrawdownResult:

        if equity is None or equity_peak is None or equity_peak <= 0:
            return DrawdownResult(
                drawdown_pct=0.0,
                multiplier=1.0,
                hard_stop=False,
            )

        dd = (equity_peak - equity) / equity_peak

        # Hard institutional breaker
        if dd >= self.HARD_LIMIT:
            return DrawdownResult(
                drawdown_pct=dd,
                multiplier=0.0,
                hard_stop=True,
            )

        # Tiered compression
        if dd < 0.05:
            mult = 1.0
        elif dd < 0.10:
            mult = 0.75
        elif dd < 0.15:
            mult = 0.50
        else:
            mult = 0.25

        return DrawdownResult(
            drawdown_pct=dd,
            multiplier=mult,
            hard_stop=False,
        )
