from __future__ import annotations

from typing import Dict, List


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class MarketRegimeEngine:
    """
    Classifies the market environment.

    Regimes:
    - TREND
    - MEAN_REVERSION
    - VOLATILE
    - NEUTRAL
    """

    def __init__(self):

        self.trend_threshold = 0.004
        self.volatility_threshold = 0.008

    def detect(self, rows: List[Dict]):

        enriched = []

        for row in rows:

            candles = row.get("candles", [])

            if len(candles) < 20:
                row["regime"] = "NEUTRAL"
                enriched.append(row)
                continue

            closes = [c["close"] for c in candles[-20:]]

            high = max(closes)
            low = min(closes)

            price = closes[-1]

            range_pct = (high - low) / price

            trend = (closes[-1] - closes[0]) / closes[0]

            regime = "NEUTRAL"

            if abs(trend) > self.trend_threshold:
                regime = "TREND"

            if range_pct > self.volatility_threshold:
                regime = "VOLATILE"

            if abs(trend) < 0.001 and range_pct < 0.004:
                regime = "MEAN_REVERSION"

            new_row = dict(row)
            new_row["regime"] = regime

            enriched.append(new_row)

        return enriched