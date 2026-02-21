"""
SignalEngine – Hybrid Regime-Aware Alpha Layer (Calibrated)
Capital Strata Systems (CSS)

Calibrations (based on harness diagnostics):
- Regime gating re-enabled with calibrated thresholds:
    * TREND gate: trend_conf >= 0.15
    * MEAN_REVERSION gate: range_conf >= 0.15
  (Previous 0.30 was too strict for this repo’s regime scale.)

- Volatility kill-switch kept:
    * high_vol_conf >= 0.70 => FLAT

- Threshold enforcement remains:
    * profile.min_signal_strength controls pass/fail (default set by caller)
  NOTE: harness showed 0.65 produced best behavior; 0.75 produced 0 trades.

Repo-compatibility:
- Does NOT import engine.regime.regime_types (not present)
- Uses string-matching on regime_conf keys for derived confidences
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
    direction: str        # "BUY" | "SELL" | "FLAT"
    strength: float       # 0.0 – 1.0
    style: str            # "TREND" | "MEAN_REVERSION" | "NONE"
    regime: Optional[str] = None
    regime_conf: Optional[Dict[str, float]] = None


# ============================================================
# SIGNAL ENGINE
# ============================================================

class SignalEngine:
    # Calibrated soft gates (matched to observed regime_conf scale)
    TREND_GATE_MIN = 0.15
    RANGE_GATE_MIN = 0.15

    # Defensive kill-switch
    HIGH_VOL_KILL = 0.70

    def __init__(self, profile: StrategyProfile, behaviour_name: str = "BALANCED"):
        self.profile = profile

        # Regime stack (raw -> smoothed)
        self.regime_model = MarketRegimeModel()
        self.regime_controller = RegimeController(behaviour=behaviour_name)

        # Price history per instrument (lightweight)
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
    def _mean_reversion_signal(self, price_now: float, moving_avg: float) -> Signal:
        if moving_avg == 0:
            return Signal("", "FLAT", 0.0, "NONE")

        deviation = (price_now - moving_avg) / moving_avg

        # deadzone
        if abs(deviation) < 0.01:
            return Signal("", "FLAT", 0.0, "NONE")

        strength = min(abs(deviation) * 10.0, 1.0)

        if deviation > 0:
            return Signal("", "SELL", strength, "MEAN_REVERSION")
        return Signal("", "BUY", strength, "MEAN_REVERSION")

    # ----------------------------------------------------------
    # Regime confidence extraction (repo-robust)
    # ----------------------------------------------------------
    def _conf_to_str_dict(self, conf: Any) -> Dict[str, float]:
        out: Dict[str, float] = {}
        if not isinstance(conf, dict):
            return out
        for k, v in conf.items():
            ks = str(k)
            try:
                out[ks] = float(v)
            except Exception:
                continue
        return out

    def _derive_regime_scores(self, conf_str: Dict[str, float]) -> Dict[str, float]:
        """
        Derive:
          - trend_conf: TREND_UP + TREND_DOWN (pattern)
          - range_conf: RANGE + LOW_VOL (pattern)
          - high_vol_conf: HIGH_VOL (pattern)
        """
        trend_conf = 0.0
        range_conf = 0.0
        high_vol_conf = 0.0

        for ks, v in conf_str.items():
            u = ks.upper()

            # Trend bucket
            if "TREND_UP" in u or "TREND_DOWN" in u or ("TREND" in u and "RANGE" not in u):
                trend_conf += v

            # Range / low vol bucket
            if "RANGE" in u or "LOW_VOL" in u or "LOWVOL" in u:
                range_conf += v

            # High vol bucket
            if "HIGH_VOL" in u or "HIGHVOL" in u or ("VOL" in u and "LOW" not in u):
                high_vol_conf += v

        # Clamp
        trend_conf = max(0.0, min(1.0, trend_conf))
        range_conf = max(0.0, min(1.0, range_conf))
        high_vol_conf = max(0.0, min(1.0, high_vol_conf))

        return {
            "trend_conf": trend_conf,
            "range_conf": range_conf,
            "high_vol_conf": high_vol_conf,
        }

    # ----------------------------------------------------------
    # Regime bias (confidence-weighted)
    # ----------------------------------------------------------
    def _apply_regime_bias(self, sig: Signal, scores: Dict[str, float]) -> Signal:
        trend_conf = float(scores.get("trend_conf", 0.0))
        range_conf = float(scores.get("range_conf", 0.0))
        high_vol_conf = float(scores.get("high_vol_conf", 0.0))

        s = float(sig.strength)

        if sig.style == "TREND":
            # Boost when trend confidence is present; add friction under high vol
            s *= (1.0 + 0.50 * trend_conf)
            s *= (1.0 - 0.40 * high_vol_conf)

        elif sig.style == "MEAN_REVERSION":
            # Boost when range confidence is present; add friction under high vol
            s *= (1.0 + 0.50 * range_conf)
            s *= (1.0 - 0.30 * high_vol_conf)

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

        # Maintain price history
        hist = self.price_history.setdefault(instrument, [])
        hist.append(float(price_now))
        if len(hist) > 60:
            del hist[0]

        # Compute raw + smoothed regime
        raw_regime = self.regime_model.evaluate(hist)
        regime = self.regime_controller.update(raw_regime)

        # Extract confidence dict safely
        conf = regime.as_dict() if hasattr(regime, "as_dict") else {}
        conf_str = self._conf_to_str_dict(conf)
        scores = self._derive_regime_scores(conf_str)

        # Volatility kill-switch (defensive)
        if scores["high_vol_conf"] >= self.HIGH_VOL_KILL:
            return Signal(
                instrument, "FLAT", 0.0, "NONE",
                getattr(regime, "dominant", lambda: None)(),
                conf_str
            )

        # Candidate signals
        candidates: List[Signal] = []

        if getattr(self.profile, "allow_trend", True):
            candidates.append(self._trend_signal(price_now, price_prev))

        if getattr(self.profile, "allow_mean_reversion", True):
            candidates.append(self._mean_reversion_signal(price_now, moving_avg))

        if not candidates:
            return Signal(
                instrument, "FLAT", 0.0, "NONE",
                getattr(regime, "dominant", lambda: None)(),
                conf_str
            )

        best = max(candidates, key=lambda s: s.strength)

        # Apply regime bias (boost/friction)
        best = self._apply_regime_bias(best, scores)

        # ------------------------------------------------------
        # Calibrated regime gating (re-enabled)
        # ------------------------------------------------------
        if best.style == "TREND" and scores["trend_conf"] < self.TREND_GATE_MIN:
            return Signal(
                instrument, "FLAT", 0.0, "NONE",
                getattr(regime, "dominant", lambda: None)(),
                conf_str
            )

        if best.style == "MEAN_REVERSION" and scores["range_conf"] < self.RANGE_GATE_MIN:
            return Signal(
                instrument, "FLAT", 0.0, "NONE",
                getattr(regime, "dominant", lambda: None)(),
                conf_str
            )

        # Threshold enforcement
        threshold = float(getattr(self.profile, "min_signal_strength", 0.0))
        if best.strength < threshold:
            return Signal(
                instrument, "FLAT", 0.0, "NONE",
                getattr(regime, "dominant", lambda: None)(),
                conf_str
            )

        # Finalize
        best.instrument = instrument
        best.regime = getattr(regime, "dominant", lambda: None)()
        best.regime_conf = conf_str
        return best