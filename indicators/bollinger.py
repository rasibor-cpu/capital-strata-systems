from __future__ import annotations

"""
REA Capital – Indicators
Bollinger Bands (pure python, deterministic, no numpy)

- Works on floats (e.g., mid prices, closes)
- Provides both:
  1) one-shot computation on a window
  2) streaming stateful calculator (rolling window)

Python: 3.14 compatible
"""

from dataclasses import dataclass, field
from typing import Deque, Iterable, List, Optional, Tuple
from collections import deque
import math


def _safe_float(x: object, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", "")
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / float(len(values))


def _std_pop(values: List[float], mu: float) -> float:
    """
    Population std dev (ddof=0) to keep deterministic, simple behavior.
    """
    n = len(values)
    if n <= 0:
        return 0.0
    var = sum((v - mu) ** 2 for v in values) / float(n)
    return math.sqrt(max(0.0, var))


@dataclass(frozen=True)
class BollingerBands:
    period: int = 20
    k: float = 2.0

    # most recent computed values
    middle: float = 0.0
    upper: float = 0.0
    lower: float = 0.0
    std: float = 0.0

    # diagnostics
    n: int = 0

    def as_dict(self) -> dict:
        return {
            "period": self.period,
            "k": self.k,
            "n": self.n,
            "middle": self.middle,
            "upper": self.upper,
            "lower": self.lower,
            "std": self.std,
        }


def compute_bollinger(window: Iterable[object], period: int = 20, k: float = 2.0) -> Optional[BollingerBands]:
    """
    One-shot computation. Expects `window` to contain at least `period` items
    (extra items are allowed; we use the most recent `period`).
    Returns None if insufficient data.
    """
    p = int(period)
    if p <= 1:
        raise ValueError("period must be >= 2")

    vals = [_safe_float(v, default=0.0) for v in window]
    # Keep only the last `period`
    if len(vals) < p:
        return None
    vals = vals[-p:]

    mu = _mean(vals)
    sd = _std_pop(vals, mu)
    up = mu + (float(k) * sd)
    lo = mu - (float(k) * sd)

    return BollingerBands(period=p, k=float(k), middle=mu, upper=up, lower=lo, std=sd, n=len(vals))


@dataclass
class BollingerState:
    """
    Streaming Bollinger Bands (rolling window).
    Push values as they arrive; when ready, latest() returns bands.
    """
    period: int = 20
    k: float = 2.0
    _buf: Deque[float] = field(default_factory=deque)

    def push(self, value: object) -> Optional[BollingerBands]:
        p = int(self.period)
        if p <= 1:
            raise ValueError("period must be >= 2")

        v = _safe_float(value, default=0.0)
        self._buf.append(v)
        while len(self._buf) > p:
            self._buf.popleft()

        if len(self._buf) < p:
            return None

        vals = list(self._buf)
        mu = _mean(vals)
        sd = _std_pop(vals, mu)
        up = mu + (float(self.k) * sd)
        lo = mu - (float(self.k) * sd)

        return BollingerBands(period=p, k=float(self.k), middle=mu, upper=up, lower=lo, std=sd, n=len(vals))

    def latest(self) -> Optional[BollingerBands]:
        if len(self._buf) < int(self.period):
            return None
        vals = list(self._buf)
        mu = _mean(vals)
        sd = _std_pop(vals, mu)
        up = mu + (float(self.k) * sd)
        lo = mu - (float(self.k) * sd)
        return BollingerBands(period=int(self.period), k=float(self.k), middle=mu, upper=up, lower=lo, std=sd, n=len(vals))

    def snapshot(self) -> dict:
        return {
            "period": int(self.period),
            "k": float(self.k),
            "count": len(self._buf),
            "values_tail": list(self._buf)[-min(5, len(self._buf)):],
        }


def bollinger_position(price: float, bands: BollingerBands) -> float:
    """
    Normalized position of price inside the bands.
    - 0.0 ~ at lower band
    - 0.5 ~ at middle
    - 1.0 ~ at upper band
    Values can be <0 or >1 if price is outside bands.
    """
    width = (bands.upper - bands.lower)
    if width == 0.0:
        return 0.5
    return (float(price) - bands.lower) / width


def bollinger_zscore(price: float, bands: BollingerBands) -> float:
    """
    Z-score vs middle band: (price - middle)/std.
    If std is zero, returns 0.
    """
    if bands.std == 0.0:
        return 0.0
    return (float(price) - bands.middle) / bands.std


if __name__ == "__main__":
    # Self-test
    prices = [1, 2, 3, 4, 5] * 5
    bb = compute_bollinger(prices, period=20, k=2.0)
    print("compute_bollinger:", None if bb is None else bb.as_dict())

    st = BollingerState(period=5, k=2.0)
    for x in [10, 11, 12, 13, 14, 15]:
        out = st.push(x)
        if out:
            print("state:", out.as_dict(), "pos=", bollinger_position(x, out), "z=", bollinger_zscore(x, out))
