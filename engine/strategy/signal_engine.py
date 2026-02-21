"""
SignalEngine – Hybrid Regime-Aware Alpha Layer (Volatility Friction Model)
Capital Strata Systems (CSS)

Changes:
- Removed hard volatility kill-switch
- Volatility now reduces signal strength (friction only)
- Regime gating preserved
- Threshold enforcement preserved

Institutional Philosophy:
- High volatility = reduce conviction
- Not automatic flat
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from engine.strategy.strategy_mode import StrategyProfile
from engine.regime.market_regime_model import MarketRegimeModel
from engine.regime.regime_controller import RegimeController


# ============================================================
# SIGNAL STRUCTURE
# ============================================================

@dataclass
class Signal:
    instrument: str
    direction: str
    strength: float
    style: str
    regime: Optional[str] = None
    regime_conf: Optional[Dict[str, float]] = None


# ============================================================
# SIGNAL ENGINE
# ============================================================

class SignalEngine:

    TREND_GATE_MIN = 0.15
    RANGE_GATE_MIN = 0.15

    # Volatility friction coefficient (reduced from previous 0.40 penalty)
    VOL_FRICTION = 0.30

    def __init__(self, profile: StrategyProfile, behaviour_name: str = "BALANCED"):
        self.profile = profile
        self.regime_model = MarketRegimeModel()
        self.regime_controller = RegimeController(behaviour=behaviour_name)
        self.price_history: Dict[str, List[float]] = {}

    # ----------------------------------------------------------
    # TREND SIGNAL
    # ----------------------------------------------------------
    def _trend_signal(self, price_now: float, price_prev: float) -> Signal:
        if price_now > price_prev:
            return Signal("", "BUY", 0.6, "TREND")
        if price_now < price_prev:
            return Signal("", "SELL", 0.6, "TREND")
        return Signal("", "FLAT", 0.0, "NONE")

    # ----------------------------------------------------------
    # MEAN REVERSION SIGNAL
    # ----------------------------------------------------------
    def _mean_reversion_signal(self, price_now: float, moving_avg: float) -> Signal:
        if moving_avg == 0:
            return Signal("", "FLAT", 0.0, "NONE")

        deviation = (price_now - moving_avg) / moving_avg

        if abs(deviation) < 0.01:
            return Signal("", "FLAT", 0.0, "NONE")

        strength = min(abs(deviation) * 10.0, 1.0)

        if deviation > 0:
            return Signal("", "SELL", strength, "MEAN_REVERSION")
        return Signal("", "BUY", strength, "MEAN_REVERSION")

    # ----------------------------------------------------------
    # CONFIDENCE HELPERS
    # ----------------------------------------------------------
    def _conf_to_str_dict(self, conf: Any) -> Dict[str, float]:
        out: Dict[str, float] = {}
        if not isinstance(conf, dict):
            return out
        for k, v in conf.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out

    def _derive_regime_scores(self, conf_str: Dict[str, float]) -> Dict[str, float]:

        trend_conf = 0.0
        range_conf = 0.0
        high_vol_conf = 0.0

        for ks, v in conf_str.items():
            u = ks.upper()

            if "TREND_UP" in u or "TREND_DOWN" in u or ("TREND" in u and "RANGE" not in u):
                trend_conf += v

            if "RANGE" in u or "LOW_VOL" in u or "LOWVOL" in u:
                range_conf += v

            if "HIGH_VOL" in u or "HIGHVOL" in u or ("VOL" in u and "LOW" not in u):
                high_vol_conf += v

        trend_conf = max(0.0, min(1.0, trend_conf))
        range_conf = max(0.0, min(1.0, range_conf))
        high_vol_conf = max(0.0, min(1.0, high_vol_conf))

        return {
            "trend_conf": trend_conf,
            "range_conf": range_conf,
            "high_vol_conf": high_vol_conf,
        }

    # ----------------------------------------------------------
    # REGIME BIAS (WITH VOL FRICTION ONLY)
    # ----------------------------------------------------------
    def _apply_regime_bias(self, sig: Signal, scores: Dict[str, float]) -> Signal:

        trend_conf = scores["trend_conf"]
        range_conf = scores["range_conf"]
        high_vol_conf = scores["high_vol_conf"]

        s = float(sig.strength)

        if sig.style == "TREND":
            s *= (1.0 + 0.50 * trend_conf)

        elif sig.style == "MEAN_REVERSION":
            s *= (1.0 + 0.50 * range_conf)

        # Volatility friction (no hard kill)
        s *= (1.0 - self.VOL_FRICTION * high_vol_conf)

        sig.strength = max(0.0, min(1.0, s))
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

        hist = self.price_history.setdefault(instrument, [])
        hist.append(float(price_now))
        if len(hist) > 60:
            del hist[0]

        raw_regime = self.regime_model.evaluate(hist)
        regime = self.regime_controller.update(raw_regime)

        conf = regime.as_dict() if hasattr(regime, "as_dict") else {}
        conf_str = self._conf_to_str_dict(conf)
        scores = self._derive_regime_scores(conf_str)

        candidates: List[Signal] = []

        if getattr(self.profile, "allow_trend", True):
            candidates.append(self._trend_signal(price_now, price_prev))

        if getattr(self.profile, "allow_mean_reversion", True):
            candidates.append(self._mean_reversion_signal(price_now, moving_avg))

        if not candidates:
            return Signal(instrument, "FLAT", 0.0, "NONE")

        best = max(candidates, key=lambda s: s.strength)
        best = self._apply_regime_bias(best, scores)

        # Regime gating preserved
        if best.style == "TREND" and scores["trend_conf"] < self.TREND_GATE_MIN:
            return Signal(instrument, "FLAT", 0.0, "NONE")

        if best.style == "MEAN_REVERSION" and scores["range_conf"] < self.RANGE_GATE_MIN:
            return Signal(instrument, "FLAT", 0.0, "NONE")

        # Profile threshold
        threshold = float(getattr(self.profile, "min_signal_strength", 0.0))
        if best.strength < threshold:
            return Signal(instrument, "FLAT", 0.0, "NONE")

        best.instrument = instrument
        best.regime = getattr(regime, "dominant", lambda: None)()
        best.regime_conf = conf_str
        return best