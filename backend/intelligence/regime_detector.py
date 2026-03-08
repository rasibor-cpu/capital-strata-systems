from dataclasses import dataclass
from typing import List


@dataclass
class CandleView:
    close: float
    high: float
    low: float


class RegimeDetector:
    def detect(self, candles: List[CandleView], i: int) -> str:
        if i < 20:
            return "UNKNOWN"

        closes = [c.close for c in candles[i - 20:i]]
        highs = [c.high for c in candles[i - 20:i]]
        lows = [c.low for c in candles[i - 20:i]]

        window_high = max(highs)
        window_low = min(lows)
        first_close = closes[0]
        last_close = closes[-1]

        if window_low <= 0:
            return "UNKNOWN"

        range_pct = (window_high - window_low) / window_low
        trend_pct = abs(last_close - first_close) / first_close if first_close > 0 else 0.0

        if range_pct < 0.015:
            return "RANGE"

        if trend_pct > 0.02:
            return "TREND"

        return "VOLATILE"