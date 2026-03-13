from __future__ import annotations

from typing import Dict, List, Any


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class LiquiditySweepDetector:
    """
    Detects stop-hunt liquidity sweeps.

    These events occur when price briefly
    breaks previous highs/lows and quickly
    returns toward equilibrium.
    """

    def __init__(self):

        self.lookback = 20
        self.threshold = 0.002  # 0.2%

    def enrich(self, rows: List[Dict[str, Any]]):

        enriched = []

        for row in rows:

            candles = row.get("candles", [])

            if len(candles) < self.lookback:
                enriched.append(row)
                continue

            highs = [c["high"] for c in candles[-self.lookback:]]
            lows = [c["low"] for c in candles[-self.lookback:]]

            recent_high = max(highs)
            recent_low = min(lows)

            price = _safe(row.get("price"))

            sweep_up = False
            sweep_down = False

            if price > recent_high * (1 + self.threshold):
                sweep_up = True

            if price < recent_low * (1 - self.threshold):
                sweep_down = True

            new_row = dict(row)

            new_row["liquidity_sweep_up"] = sweep_up
            new_row["liquidity_sweep_down"] = sweep_down

            enriched.append(new_row)

        return enriched