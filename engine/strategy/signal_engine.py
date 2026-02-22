"""
engine/strategy/signal_engine.py

SignalEngine – Hybrid Regime-Aware Alpha Layer (Composite Strength v2)
---------------------------------------------------------------------
Purpose:
- Produce BUY / SELL / FLAT signals
- Produce a strength score (0.0 – 1.0) that is:
    * Multi-asset comparable (ATR / volatility normalized)
    * Hybrid: deterministic core + rolling normalization
    * More expressive (upper tail exists, so minsig=0.70 becomes meaningful)

Composite Strength Components (0..1):
- MomentumScore    (w=0.40): ATR-normalized distance from MA + MA slope proxy
- VolatilityScore  (w=0.25): ATR_fast vs ATR_slow expansion factor
- PersistenceScore (w=0.25): directional streak confidence
- StructureScore   (w=0.10): reserved (kept minimal to avoid scope creep)

Notes:
- Inputs available in replay are only price_now, price_prev, moving_avg.
  No OHLC => true range approximated using abs(price change).
- Per-instrument rolling state is maintained in-memory (safe for replay).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Deque, Optional
from collections import deque
import math

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
# INTERNAL HELPERS
# ============================================================

def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _sigmoid01(x: float, k: float = 1.0) -> float:
    """
    Smoothly map real-valued x to (0,1).
    k controls steepness.
    """
    # Avoid overflow for large magnitude
    x = _clamp(x, -60.0, 60.0)
    return 1.0 / (1.0 + math.exp(-k * x))


def _safe_div(a: float, b: float, eps: float = 1e-12) -> float:
    return a / (b if abs(b) > eps else eps)


# ============================================================
# ROLLING STATE PER INSTRUMENT
# ============================================================

class _InstrumentState:
    def __init__(self, atr_fast_alpha: float, atr_slow_alpha: float, ret_window: int):
        self.last_price: Optional[float] = None

        # ATR proxies (no OHLC => use abs price change)
        self.atr_fast: Optional[float] = None
        self.atr_slow: Optional[float] = None
        self.atr_fast_alpha = atr_fast_alpha
        self.atr_slow_alpha = atr_slow_alpha

        # Return history for volatility normalization
        self.returns: Deque[float] = deque(maxlen=ret_window)

        # Persistence tracking
        self.last_dir: str = "FLAT"
        self.streak: int = 0


# ============================================================
# SIGNAL ENGINE
# ============================================================

class SignalEngine:
    """
    Hybrid composite strength engine.

    Direction:
      - BUY if price_now > moving_avg
      - SELL if price_now < moving_avg
      - FLAT otherwise

    Strength:
      - Composite of (momentum, volatility regime, persistence)
      - Output is 0..1 with a healthy upper tail.
    """

    # Default institutional weights (sum to 1.0)
    W_MOMENTUM = 0.40
    W_VOL = 0.25
    W_PERSIST = 0.25
    W_STRUCTURE = 0.10

    def __init__(self, profile: StrategyProfile):
        self.profile = profile
        self._state: Dict[str, _InstrumentState] = {}

        # Rolling settings (hybrid)
        self._ret_window = 60

        # ATR EMA alphas (fast reacts, slow defines regime baseline)
        # 2/(N+1): N~14 fast, N~60 slow
        self._atr_fast_alpha = 2.0 / (14.0 + 1.0)
        self._atr_slow_alpha = 2.0 / (60.0 + 1.0)

        # Style thresholds (kept simple)
        self._trend_z_thresh = 1.25     # > => TREND
        self._mr_z_thresh = 0.60        # < => MEAN_REVERSION tendency

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    def _get_state(self, instrument: str) -> _InstrumentState:
        st = self._state.get(instrument)
        if st is None:
            st = _InstrumentState(
                atr_fast_alpha=self._atr_fast_alpha,
                atr_slow_alpha=self._atr_slow_alpha,
                ret_window=self._ret_window
            )
            self._state[instrument] = st
        return st

    # --------------------------------------------------------
    # COMPONENT SCORES (0..1)
    # --------------------------------------------------------

    def _update_atr_and_returns(self, st: _InstrumentState, price_now: float, price_prev: float) -> None:
        # Proxy for true range: abs change
        tr = abs(price_now - price_prev)

        # Returns for volatility normalization (simple log-ish return proxy)
        r = _safe_div(price_now - price_prev, price_prev)
        st.returns.append(float(r))

        # ATR EMA updates
        if st.atr_fast is None:
            st.atr_fast = tr
        else:
            st.atr_fast = (st.atr_fast_alpha * tr) + ((1.0 - st.atr_fast_alpha) * st.atr_fast)

        if st.atr_slow is None:
            st.atr_slow = tr
        else:
            st.atr_slow = (st.atr_slow_alpha * tr) + ((1.0 - st.atr_slow_alpha) * st.atr_slow)

    def _vol_norm(self, st: _InstrumentState) -> float:
        """
        Rolling volatility proxy (std of returns). Used to stabilize scoring across assets.
        Returns a strictly positive scale.
        """
        if len(st.returns) < 10:
            return 1e-6

        # Compute std (population)
        mean = sum(st.returns) / float(len(st.returns))
        var = sum((x - mean) ** 2 for x in st.returns) / float(len(st.returns))
        std = math.sqrt(max(var, 1e-12))
        return std

    def _momentum_score(self, st: _InstrumentState, price_now: float, moving_avg: float, price_prev: float) -> float:
        """
        MomentumScore combines:
        - Distance from moving_avg normalized by ATR_fast (dominant)
        - Slope proxy: change in moving_avg relative to ATR_fast (light)
        """
        atr = float(st.atr_fast) if st.atr_fast is not None else abs(price_now - price_prev)
        atr = max(atr, 1e-9)

        dist = price_now - moving_avg
        z_dist = dist / atr  # ATR-normalized distance

        # slope proxy: how fast price is moving relative to MA, normalized
        slope = (moving_avg - price_prev) / atr

        # We want strong momentum when abs(z_dist) is high AND slope confirms direction
        # Use sigmoid on abs(z_dist), then add a small directional confirmation boost
        base = _sigmoid01(abs(z_dist) - 0.5, k=1.6)  # shift so small moves are muted

        # Confirmation: if slope has same sign as dist, boost slightly
        confirm = 0.10 if (dist * slope) > 0 else 0.0

        return _clamp(base + confirm, 0.0, 1.0)

    def _volatility_score(self, st: _InstrumentState) -> float:
        """
        VolatilityScore rewards expansion relative to baseline:
        - ratio = atr_fast / atr_slow
        - ratio > 1 => expanding
        """
        if st.atr_fast is None or st.atr_slow is None:
            return 0.5

        ratio = _safe_div(float(st.atr_fast), float(st.atr_slow))
        # Map ratio into score: ratio=1 -> ~0.5, ratio=1.25 -> higher, ratio=0.8 -> lower
        return _clamp(_sigmoid01((ratio - 1.0) * 4.0, k=1.0), 0.0, 1.0)

    def _persistence_score(self, st: _InstrumentState, direction: str) -> float:
        """
        PersistenceScore: directional streak mapped to 0..1.
        A longer consistent streak increases confidence.
        """
        if direction == "FLAT":
            st.last_dir = "FLAT"
            st.streak = 0
            return 0.0

        if st.last_dir == direction:
            st.streak += 1
        else:
            st.last_dir = direction
            st.streak = 1

        # Map streak to score (fast rise then saturate)
        # 1 -> ~0.35, 3 -> ~0.65, 6 -> ~0.85, 10 -> ~0.95
        return _clamp(_sigmoid01((float(st.streak) - 1.0) * 0.55, k=1.0), 0.0, 1.0)

    def _structure_score(self, st: _InstrumentState) -> float:
        """
        StructureScore: placeholder for later.
        Keep minimal to avoid scope creep.
        """
        return 0.50

    # --------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------

    def generate(self, instrument: str, price_now: float, price_prev: float, moving_avg: float) -> Signal:
        st = self._get_state(instrument)

        # Update rolling metrics first
        self._update_atr_and_returns(st, float(price_now), float(price_prev))

        # Direction
        if price_now > moving_avg:
            direction = "BUY"
        elif price_now < moving_avg:
            direction = "SELL"
        else:
            direction = "FLAT"

        if direction == "FLAT":
            return Signal(instrument=instrument, direction="FLAT", strength=0.0, style="NONE")

        # Component scores (0..1)
        mom = self._momentum_score(st, float(price_now), float(moving_avg), float(price_prev))
        vol = self._volatility_score(st)
        per = self._persistence_score(st, direction)
        stru = self._structure_score(st)

        # Composite strength
        strength = (
            (self.W_MOMENTUM * mom) +
            (self.W_VOL * vol) +
            (self.W_PERSIST * per) +
            (self.W_STRUCTURE * stru)
        )
        strength = _clamp(float(strength), 0.0, 1.0)

        # Style classification based on normalized distance (z-like)
        atr = float(st.atr_fast) if st.atr_fast is not None else abs(price_now - price_prev)
        atr = max(atr, 1e-9)
        z = abs((price_now - moving_avg) / atr)

        if z >= self._trend_z_thresh:
            style = "TREND"
        elif z <= self._mr_z_thresh:
            style = "MEAN_REVERSION"
        else:
            style = "NONE"

        return Signal(instrument=instrument, direction=direction, strength=strength, style=style)