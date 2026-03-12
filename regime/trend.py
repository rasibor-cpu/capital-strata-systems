from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from data.models import Bar


@dataclass
class TrendPolicy:
    """
    Unified CSS trend policy.

    Supports:
    - trend-day risk detection for mean reversion blocking
    - trend strength confirmation for trend-following execution

    Core measures:
    - directional efficiency
    - EMA alignment
    - slope strength
    """
    window: int = 18  # last 18 x 5m = 90 minutes
    efficiency_threshold: float = 0.52
    fast_ema_period: int = 9
    mid_ema_period: int = 21
    slow_ema_period: int = 50
    slope_lookback: int = 5
    min_slope: float = 0.0


@dataclass
class TrendStrengthResult:
    trend_allowed: bool
    trend_direction: str
    efficiency: Optional[float]
    slope: Optional[float]
    fast_ema: Optional[float]
    mid_ema: Optional[float]
    slow_ema: Optional[float]
    reason: str


def _ema(values: List[float], period: int) -> Optional[float]:
    if not values:
        return None

    if len(values) < period:
        return values[-1]

    multiplier = 2.0 / (period + 1.0)
    ema = values[0]

    for v in values:
        ema = ((v - ema) * multiplier) + ema

    return ema


def _slope(values: List[float], lookback: int) -> Optional[float]:
    if len(values) < lookback:
        return None

    recent = values[-lookback:]
    n = len(recent)
    x = list(range(n))

    mean_x = sum(x) / n
    mean_y = sum(recent) / n

    numerator = sum((x[i] - mean_x) * (recent[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return numerator / denominator


def trend_day_check(
    bars_5m: List[Bar],
    policy: TrendPolicy,
) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Backward-compatible trend-day risk check.

    Returns:
      (is_trending, reason_if_trending, efficiency)

    bars_5m must be chronological order (oldest -> newest)
    """
    if len(bars_5m) < policy.window + 1:
        return True, "Insufficient 5m bars for trend check.", None

    w = bars_5m[-(policy.window + 1):]
    closes = [b.c for b in w]

    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    denom = sum(abs(x) for x in diffs)
    if denom == 0:
        return False, None, 0.0

    net = closes[-1] - closes[0]
    efficiency = abs(net) / denom

    if efficiency >= policy.efficiency_threshold:
        return (
            True,
            f"Trend-day risk: efficiency {efficiency:.2f} >= {policy.efficiency_threshold:.2f}",
            efficiency,
        )

    return False, None, efficiency


def evaluate_trend_strength(
    bars_5m: List[Bar],
    policy: TrendPolicy,
) -> TrendStrengthResult:
    """
    Canonical trend-strength evaluator for CSS.

    Returns a richer decision object for:
    - allowing trend-following trades
    - blocking weak/choppy markets
    """
    closes = [b.c for b in bars_5m]

    required = max(
        policy.window + 1,
        policy.slow_ema_period,
        policy.slope_lookback,
    )

    if len(closes) < required:
        return TrendStrengthResult(
            trend_allowed=False,
            trend_direction="UNKNOWN",
            efficiency=None,
            slope=None,
            fast_ema=None,
            mid_ema=None,
            slow_ema=None,
            reason="insufficient history",
        )

    w = closes[-(policy.window + 1):]
    diffs = [w[i] - w[i - 1] for i in range(1, len(w))]
    denom = sum(abs(x) for x in diffs)

    if denom == 0:
        return TrendStrengthResult(
            trend_allowed=False,
            trend_direction="FLAT",
            efficiency=0.0,
            slope=0.0,
            fast_ema=None,
            mid_ema=None,
            slow_ema=None,
            reason="flat market",
        )

    net = w[-1] - w[0]
    efficiency = abs(net) / denom

    fast_ema = _ema(closes, policy.fast_ema_period)
    mid_ema = _ema(closes, policy.mid_ema_period)
    slow_ema = _ema(closes, policy.slow_ema_period)
    slope = _slope(closes, policy.slope_lookback)

    last_price = closes[-1]

    bullish = (
        fast_ema is not None and
        mid_ema is not None and
        slow_ema is not None and
        fast_ema > mid_ema > slow_ema and
        last_price >= fast_ema
    )

    bearish = (
        fast_ema is not None and
        mid_ema is not None and
        slow_ema is not None and
        fast_ema < mid_ema < slow_ema and
        last_price <= fast_ema
    )

    if bullish:
        direction = "BULLISH"
    elif bearish:
        direction = "BEARISH"
    else:
        direction = "SIDEWAYS"

    if efficiency < policy.efficiency_threshold:
        return TrendStrengthResult(
            trend_allowed=False,
            trend_direction=direction,
            efficiency=efficiency,
            slope=slope,
            fast_ema=fast_ema,
            mid_ema=mid_ema,
            slow_ema=slow_ema,
            reason=f"weak directional efficiency {efficiency:.2f}",
        )

    if slope is None or slope <= policy.min_slope:
        return TrendStrengthResult(
            trend_allowed=False,
            trend_direction=direction,
            efficiency=efficiency,
            slope=slope,
            fast_ema=fast_ema,
            mid_ema=mid_ema,
            slow_ema=slow_ema,
            reason="momentum slope not supportive",
        )

    if direction == "SIDEWAYS":
        return TrendStrengthResult(
            trend_allowed=False,
            trend_direction=direction,
            efficiency=efficiency,
            slope=slope,
            fast_ema=fast_ema,
            mid_ema=mid_ema,
            slow_ema=slow_ema,
            reason="ema structure not directional",
        )

    return TrendStrengthResult(
        trend_allowed=True,
        trend_direction=direction,
        efficiency=efficiency,
        slope=slope,
        fast_ema=fast_ema,
        mid_ema=mid_ema,
        slow_ema=slow_ema,
        reason="trend strong",
    )