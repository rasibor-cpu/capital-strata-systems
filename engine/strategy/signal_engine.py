"""
SignalEngine – Hybrid Regime-Aware Alpha Layer
Capital Strata Systems (CSS)

Generates:
- BUY / SELL / FLAT
- Signal strength (0.0 – 1.0)

Respects StrategyProfile:
- Thresholds
- Allowed styles
- Trade frequency bias
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from engine.strategy.strategy_mode import StrategyProfile


# ============================================================
# SIGNAL STRUCTURE
# ============================================================

@dataclass
class Signal:
    instrument: str
    direction: str        # "BUY" | "SELL" | "FLAT"
    strength: float       # 0.0 – 1.0
    style: str            # "TREND" | "MEAN_REVERSION" | "NONE"


# ============================================================
# SIGNAL ENGINE
# ============================================================

class SignalEngine:

    def __init__(self, profile: StrategyProfile):
        self.profile = profile

    # ----------------------------------------------------------
    # SYNTHETIC TREND DETECTOR
    # ----------------------------------------------------------

    def _trend_signal(self, price_now: float, price_prev: float) -> Signal:

        if price_now > price_prev:
            return Signal("", "BUY", 0.6, "TREND")

        if price_now < price_prev:
            return Signal("", "SELL", 0.6, "TREND")

        return Signal("", "FLAT", 0.0, "NONE")

    # ----------------------------------------------------------
    # SYNTHETIC MEAN REVERSION DETECTOR
    # ----------------------------------------------------------

    def _mean_reversion_signal(
        self,
        price_now: float,
        moving_avg: float,
    ) -> Signal:

        deviation = (price_now - moving_avg) / moving_avg

        if deviation > 0.01:
            return Signal("", "SELL", min(abs(deviation) * 10, 1.0), "MEAN_REVERSION")

        if deviation < -0.01:
            return Signal("", "BUY", min(abs(deviation) * 10, 1.0), "MEAN_REVERSION")

        return Signal("", "FLAT", 0.0, "NONE")

    # ----------------------------------------------------------
    # PUBLIC INTERFACE
    # ----------------------------------------------------------

    def generate(
        self,
        instrument: str,
        price_now: float,
        price_prev: float,
        moving_avg: float,
    ) -> Signal:

        candidate_signals = []

        # Trend allowed?
        if self.profile.allow_trend:
            candidate_signals.append(
                self._trend_signal(price_now, price_prev)
            )

        # Mean reversion allowed?
        if self.profile.allow_mean_reversion:
            candidate_signals.append(
                self._mean_reversion_signal(price_now, moving_avg)
            )

        # Choose strongest
        best = max(candidate_signals, key=lambda s: s.strength)

        # Apply threshold filter
        if best.strength < self.profile.min_signal_strength:
            return Signal(instrument, "FLAT", 0.0, "NONE")

        return Signal(instrument, best.direction, best.strength, best.style)