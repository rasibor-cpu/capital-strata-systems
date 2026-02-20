"""
SignalEngine – Hybrid Regime-Aware Alpha Layer (v2)
Capital Strata Systems (CSS)

Generates:
- BUY / SELL / FLAT
- Signal strength (0.0 – 1.0)
- style: TREND / MEAN_REVERSION / NONE

Upgrades:
- Integrates MarketRegimeModel + RegimeController (EMA smoothing)
- Uses regime confidence to bias signal strengths (no hard switching)
- Keeps SignalEngine interface simple for EngineLoop
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from engine.strategy.strategy_mode import StrategyProfile
from engine.regime.market_regime_model import MarketRegimeModel
from engine.regime.regime_controller import RegimeController
from engine.regime.regime_state import (
    TREND_UP,
    TREND_DOWN,
    RANGE,
    HIGH_VOLATILITY,
    LOW_VOLATILITY,
    RegimeConfidence,
)


# ============================================================
# SIGNAL STRUCTURE
# ============================================================

@dataclass
class Signal:
    instrument: str
    direction: str        # "BUY" | "SELL" | "FLAT"
    strength: float       # 0.0 – 1.0
    style: str            # "TREND" | "MEAN_REVERSION" | "NONE"
    regime: Optional[str] = None
    regime_conf: Optional[Dict[str, float]] = None


# ============================================================
# SIGNAL ENGINE
# ============================================================

class SignalEngine:

    def __init__(self, profile: StrategyProfile, behaviour_name: str = "BALANCED"):
        self.profile = profile

        # Regime stack (raw + smoothed)
        self.regime_model = MarketRegimeModel()
        self.regime_controller = RegimeController(behaviour=behaviour_name)

        # Price history per instrument (lightweight memory)
        self.price_history: Dict[str, List[float]] = {}

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
    # REGIME BIAS (CONFIDENCE-WEIGHTED)
    # ----------------------------------------------------------

    def _apply_regime_bias(self, sig: Signal, regime: RegimeConfidence) -> Signal:
        """
        Bias logic (soft):
        - Trend signals are boosted when TREND_UP/TREND_DOWN confidence is high
        - Mean reversion signals are boosted when RANGE or LOW_VOLATILITY is high
        - High volatility reduces overall strength (defensive friction)
        """

        conf = regime.as_dict()

        trend_conf = conf.get(TREND_UP, 0.0) + conf.get(TREND_DOWN, 0.0)
        range_conf = conf.get(RANGE, 0.0) + conf.get(LOW_VOLATILITY, 0.0)
        high_vol_conf = conf.get(HIGH_VOLATILITY, 0.0)

        strength = float(sig.strength)

        if sig.style == "TREND":
            strength *= (1.0 + 0.75 * trend_conf)
            strength *= (1.0 - 0.50 * high_vol_conf)

        elif sig.style == "MEAN_REVERSION":
            strength *= (1.0 + 0.75 * range_conf)
            strength *= (1.0 - 0.35 * high_vol_conf)

        # clamp
        strength = max(0.0, min(1.0, strength))

        sig.strength = strength
        sig.regime = regime.dominant()
        sig.regime_conf = conf
        return sig

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

        # Maintain price history
        hist = self.price_history.setdefault(instrument, [])
        hist.append(float(price_now))
        if len(hist) > 60:
            del hist[: len(hist) - 60]

        # Compute raw + smoothed regime
        raw_regime = self.regime_model.evaluate(hist)
        smoothed_regime = self.regime_controller.update(raw_regime)

        candidate_signals: List[Signal] = []

        # Trend allowed?
        if getattr(self.profile, "allow_trend", True):
            candidate_signals.append(self._trend_signal(price_now, price_prev))

        # Mean reversion allowed?
        if getattr(self.profile, "allow_mean_reversion", True):
            candidate_signals.append(self._mean_reversion_signal(price_now, moving_avg))

        # Choose strongest (pre-bias)
        best = max(candidate_signals, key=lambda s: s.strength)

        # Apply regime bias (soft)
        best = self._apply_regime_bias(best, smoothed_regime)

        # Apply threshold filter
        if best.strength < float(getattr(self.profile, "min_signal_strength", 0.0)):
            return Signal(instrument, "FLAT", 0.0, "NONE", smoothed_regime.dominant(), smoothed_regime.as_dict())

        return Signal(instrument, best.direction, best.strength, best.style, best.regime, best.regime_conf)