from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from data.models import Bar


@dataclass
class TrendPolicy:
    """
    Simple 5-minute trend-day detection.

    We measure:
    - directional efficiency: abs(net_change) / sum(abs(incremental_changes))
    - if efficiency is high, price is moving persistently in one direction (trend-day risk)

    Thresholds are intentionally conservative; we will calibrate later.
    """
    window: int = 18  # last 18 x 5m = 90 minutes
    efficiency_threshold: float = 0.62  # higher = more trend-like


def trend_day_check(bars_5m: List[Bar], policy: TrendPolicy) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Returns:
      (is_trending, reason_if_trending, efficiency)
    bars_5m: chronological order (oldest -> newest)
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
    efficiency = abs(net) / denom  # 0..1

    if efficiency >= policy.efficiency_threshold:
        return True, f"Trend-day risk: efficiency {efficiency:.2f} >= {policy.efficiency_threshold:.2f}", efficiency

    return False, None, efficiency
