from __future__ import annotations

from typing import Dict, List, Any


def _safe(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


class LiquiditySweepDetector:
    """
    CSS Liquidity Sweep Detector

    Detects stop-hunt liquidity sweeps where price
    briefly violates recent highs/lows before returning.

    Designed to be robust across candle formats:
    - dict candles
    - object candles
    - tuple/list candles
    """

    def __init__(self):

        self.lookback = 20
        self.threshold = 0.002  # 0.2%

    # ---------------------------------------------------------
    # SAFE CANDLE ACCESS
    # ---------------------------------------------------------

    def _attr(self, candle: Any, name: str):

        # dict candles
        if isinstance(candle, dict):
            return _safe(candle.get(name))

        # object candles
        if hasattr(candle, name):
            return _safe(getattr(candle, name))

        # tuple/list candles
        if isinstance(candle, (list, tuple)):

            idx_map = {
                "ts": 0,
                "open": 1,
                "high": 2,
                "low": 3,
                "close": 4,
                "volume": 5,
            }

            idx = idx_map.get(name)

            if idx is not None and len(candle) > idx:
                return _safe(candle[idx])

        return 0.0

    # ---------------------------------------------------------
    # CORE LOGIC
    # ---------------------------------------------------------

    def enrich(self, rows: List[Dict[str, Any]]):

        enriched = []

        for row in rows:

            candles = row.get("candles", [])

            if len(candles) < self.lookback:
                enriched.append(row)
                continue

            subset = candles[-self.lookback:]

            highs = [self._attr(c, "high") for c in subset]
            lows = [self._attr(c, "low") for c in subset]

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

    # ---------------------------------------------------------
    # PIPELINE COMPATIBILITY
    # ---------------------------------------------------------

    def enrich_rows(self, rows: List[Dict[str, Any]]):
        """
        Adapter so the detector fits the CSS pipeline contract.

        Dashboard expects every engine to expose:
            enrich_rows(rows)

        This simply routes to enrich().
        """

        return self.enrich(rows)