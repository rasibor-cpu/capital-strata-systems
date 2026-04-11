from __future__ import annotations

from typing import Any, Dict, List


class MarketRegimeEngine:
    """
    CSS Market Regime Engine

    Detects broad market state from recent candles and enriches rows with:
    - regime
    - regime_score
    - trend_strength
    - range_score
    - volatility_score
    - directional_bias
    - regime_gate_pass

    Regimes:
    - VOLATILE
    - BREAKOUT
    - TREND
    - RANGE
    - MEAN_REVERSION
    - NEUTRAL
    """

    def __init__(self) -> None:
        pass

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _attr(self, candle: Any, name: str, default: float = 0.0) -> float:
        if isinstance(candle, dict):
            return self._safe_float(candle.get(name), default)

        if hasattr(candle, name):
            return self._safe_float(getattr(candle, name), default)

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
                return self._safe_float(candle[idx], default)

        return default

    def _get_close(self, candle: Any) -> float:
        return self._attr(candle, "close")

    def _get_high(self, candle: Any) -> float:
        return self._attr(candle, "high")

    def _get_low(self, candle: Any) -> float:
        return self._attr(candle, "low")

    def _get_open(self, candle: Any) -> float:
        return self._attr(candle, "open")

    def _get_range_volatility(self, candles: List[Any]) -> float:
        if not candles:
            return 0.0

        rel_ranges: List[float] = []

        for c in candles:
            high = self._get_high(c)
            low = self._get_low(c)
            close = self._get_close(c)

            if close > 0 and high >= low:
                rel_ranges.append((high - low) / close)

        if not rel_ranges:
            return 0.0

        return sum(rel_ranges) / len(rel_ranges)

    def _directional_bias(self, closes: List[float]) -> str:
        if len(closes) < 2:
            return "FLAT"

        delta = closes[-1] - closes[0]
        if delta > 0:
            return "UP"
        if delta < 0:
            return "DOWN"
        return "FLAT"

    def _trend_consistency(self, closes: List[float]) -> float:
        if len(closes) < 3:
            return 0.0

        up = 0
        down = 0

        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                up += 1
            elif closes[i] < closes[i - 1]:
                down += 1

        total = up + down
        if total <= 0:
            return 0.0

        return abs(up - down) / total

    def _detect_regime_from_candles(self, candles: List[Any]) -> Dict[str, Any]:
        if len(candles) < 20:
            return {
                "regime": "NEUTRAL",
                "regime_score": 0.0,
                "trend_strength": 0.0,
                "range_score": 0.0,
                "volatility_score": 0.0,
                "directional_bias": "FLAT",
                "regime_gate_pass": False,
            }

        subset = candles[-20:]

        closes = [self._get_close(c) for c in subset]
        highs = [self._get_high(c) for c in subset]
        lows = [self._get_low(c) for c in subset]

        closes = [x for x in closes if x > 0]
        highs = [x for x in highs if x > 0]
        lows = [x for x in lows if x > 0]

        if len(closes) < 5 or not highs or not lows:
            return {
                "regime": "NEUTRAL",
                "regime_score": 0.0,
                "trend_strength": 0.0,
                "range_score": 0.0,
                "volatility_score": 0.0,
                "directional_bias": "FLAT",
                "regime_gate_pass": False,
            }

        first_close = closes[0]
        last_close = closes[-1]

        trend_strength = 0.0
        if first_close > 0:
            trend_strength = abs(last_close - first_close) / first_close

        total_high = max(highs)
        total_low = min(lows)

        range_score = 0.0
        if last_close > 0 and total_high >= total_low:
            range_score = (total_high - total_low) / last_close

        volatility_score = self._get_range_volatility(subset)
        directional_bias = self._directional_bias(closes)
        consistency_score = self._trend_consistency(closes)

        if volatility_score >= 0.035:
            regime = "VOLATILE"
            regime_score = min(volatility_score * 8.0, 1.0)

        elif trend_strength >= 0.020 and consistency_score >= 0.35:
            if volatility_score >= 0.025:
                regime = "BREAKOUT"
                regime_score = min((trend_strength + volatility_score + consistency_score) * 8.0, 1.0)
            else:
                regime = "TREND"
                regime_score = min((trend_strength * 14.0) + (consistency_score * 0.3), 1.0)

        elif trend_strength <= 0.010 and volatility_score <= 0.018:
            regime = "MEAN_REVERSION"
            regime_score = min((0.018 - volatility_score) / 0.018, 1.0)

        elif range_score <= 0.030:
            regime = "RANGE"
            regime_score = min((0.03 - range_score) / 0.03, 1.0)

        else:
            regime = "NEUTRAL"
            regime_score = 0.5

        regime_gate_pass = regime in {"TREND", "BREAKOUT", "VOLATILE", "MEAN_REVERSION"}

        return {
            "regime": regime,
            "regime_score": max(0.0, min(regime_score, 1.0)),
            "trend_strength": trend_strength,
            "range_score": range_score,
            "volatility_score": volatility_score,
            "directional_bias": directional_bias,
            "consistency_score": consistency_score,
            "regime_gate_pass": regime_gate_pass,
        }

    def detect_one(self, candles: List[Any]) -> Dict[str, Any]:
        return self._detect_regime_from_candles(candles)

    def detect(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            candles = row.get("candles", [])
            regime_info = self._detect_regime_from_candles(candles)

            new_row = dict(row)
            new_row.update(regime_info)

            enriched.append(new_row)

        return enriched