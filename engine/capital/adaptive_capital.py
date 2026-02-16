"""
Adaptive Capital Scaling Engine
Capital Strata Systems

Purpose:
Dynamic capital allocation based on:

- Drawdown level
- Loss streak
- Regime
- Volatility normalization
- Controlled compounding principles

Fail-closed by design.
"""

from __future__ import annotations

from typing import Dict


class AdaptiveCapitalEngine:
    """
    Produces a capital multiplier (0.0 → 1.0+)

    Multiplier is applied to base policy capital.
    """

    def __init__(self) -> None:
        pass

    # ---------------------------------------------------------
    # CORE LOGIC
    # ---------------------------------------------------------

    def compute_multiplier(
        self,
        *,
        equity: float | None,
        equity_peak: float | None,
        consecutive_losses: int,
        regime: str | None,
        volatility_ratio: float | None = None,
    ) -> Dict[str, float | str]:

        if equity is None or equity_peak is None:
            return {
                "multiplier": 0.0,
                "reason": "missing_equity_data",
            }

        if equity_peak <= 0:
            return {
                "multiplier": 0.0,
                "reason": "invalid_peak",
            }

        drawdown = (equity_peak - equity) / equity_peak

        multiplier = 1.0
        reason = "base"

        # ---------------------------------
        # Drawdown Compression
        # ---------------------------------
        if drawdown >= 0.10:
            multiplier *= 0.5
            reason = "drawdown_10pct"

        elif drawdown >= 0.05:
            multiplier *= 0.75
            reason = "drawdown_5pct"

        # ---------------------------------
        # Loss Streak Compression
        # ---------------------------------
        if consecutive_losses >= 3:
            multiplier *= 0.7
            reason = "loss_streak_3"

        if consecutive_losses >= 5:
            multiplier *= 0.5
            reason = "loss_streak_5"

        # ---------------------------------
        # Regime Influence
        # ---------------------------------
        if regime == "DEFENSIVE":
            multiplier *= 0.6
            reason = "defensive_regime"

        if regime == "AGGRESSIVE":
            multiplier *= 1.1
            reason = "aggressive_regime"

        # ---------------------------------
        # Volatility Suppression
        # ---------------------------------
        if volatility_ratio is not None:
            if volatility_ratio > 2.0:
                multiplier *= 0.6
                reason = "extreme_volatility"
            elif volatility_ratio > 1.5:
                multiplier *= 0.8
                reason = "elevated_volatility"

        # Safety clamp
        multiplier = max(0.0, min(multiplier, 1.5))

        return {
            "multiplier": round(multiplier, 4),
            "reason": reason,
            "drawdown": round(drawdown, 4),
        }
