from __future__ import annotations

import math
from typing import Any, Mapping


class MarketRegimeEngine:
    """Canonical market regime classifier with feature extraction."""

    REGIMES = {
        "TRENDING",
        "RANGING",
        "BREAKOUT",
        "REVERSAL",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "UNKNOWN",
    }

    def __init__(self) -> None:
        self.high_volatility_threshold = 0.03
        self.low_volatility_threshold = 0.005
        self.trending_threshold = 0.015
        self.breakout_momentum_threshold = 0.012
        self.reversal_momentum_threshold = 0.01

    def analyze_market(self, candles: list[Mapping[str, Any]]) -> dict[str, Any]:
        features = self.extract_features(candles)
        regime, confidence = self.classify_regime(features)

        payload = dict(features)
        payload["market_regime"] = regime
        payload["confidence"] = max(0.0, min(float(confidence), 1.0))
        return payload

    def extract_features(self, candles: list[Mapping[str, Any]]) -> dict[str, Any]:
        if not candles or len(candles) < 3:
            return {
                "ATR": 0.0,
                "volatility": 0.0,
                "trend_strength": 0.0,
                "momentum": 0.0,
                "volume_state": "UNKNOWN",
                "price_acceleration": 0.0,
                "direction": "FLAT",
                "confidence": 0.0,
            }

        closes = [self._safe_float(c.get("close")) for c in candles]
        highs = [self._safe_float(c.get("high")) for c in candles]
        lows = [self._safe_float(c.get("low")) for c in candles]
        volumes = [self._safe_float(c.get("volume")) for c in candles]

        if any(value <= 0 for value in closes[-3:]):
            return {
                "ATR": 0.0,
                "volatility": 0.0,
                "trend_strength": 0.0,
                "momentum": 0.0,
                "volume_state": "UNKNOWN",
                "price_acceleration": 0.0,
                "direction": "FLAT",
                "confidence": 0.0,
            }

        true_ranges: list[float] = []
        for index in range(1, len(candles)):
            current_high = highs[index]
            current_low = lows[index]
            previous_close = closes[index - 1]
            true_range = max(
                current_high - current_low,
                abs(current_high - previous_close),
                abs(current_low - previous_close),
            )
            true_ranges.append(max(0.0, true_range))

        atr = sum(true_ranges[-14:]) / max(1, len(true_ranges[-14:]))

        returns: list[float] = []
        for index in range(1, len(closes)):
            prev = closes[index - 1]
            curr = closes[index]
            if prev <= 0:
                continue
            returns.append((curr - prev) / prev)

        volatility = self._stddev(returns)

        start_close = closes[0]
        end_close = closes[-1]
        trend_strength = abs((end_close - start_close) / start_close) if start_close > 0 else 0.0

        momentum = returns[-1] if returns else 0.0
        prior_momentum = returns[-2] if len(returns) > 1 else 0.0
        price_acceleration = momentum - prior_momentum

        avg_volume = sum(volumes) / max(1, len(volumes))
        last_volume = volumes[-1]
        if avg_volume <= 0:
            volume_state = "UNKNOWN"
        elif last_volume >= avg_volume * 1.2:
            volume_state = "HIGH"
        elif last_volume <= avg_volume * 0.8:
            volume_state = "LOW"
        else:
            volume_state = "NORMAL"

        direction = "FLAT"
        if momentum > 0:
            direction = "UP"
        elif momentum < 0:
            direction = "DOWN"

        base_confidence = min(1.0, max(volatility, trend_strength, abs(momentum) * 2.0))

        return {
            "ATR": max(0.0, atr),
            "volatility": max(0.0, volatility),
            "trend_strength": max(0.0, trend_strength),
            "momentum": momentum,
            "volume_state": volume_state,
            "price_acceleration": price_acceleration,
            "direction": direction,
            "confidence": base_confidence,
        }

    def classify_regime(self, features: Mapping[str, Any]) -> tuple[str, float]:
        volatility = self._safe_float(features.get("volatility"))
        trend_strength = self._safe_float(features.get("trend_strength"))
        momentum = self._safe_float(features.get("momentum"))
        acceleration = self._safe_float(features.get("price_acceleration"))
        direction = str(features.get("direction") or "FLAT").upper()

        if volatility <= 0 and trend_strength <= 0 and momentum == 0:
            return "UNKNOWN", 0.0

        if volatility >= self.high_volatility_threshold:
            return "HIGH_VOLATILITY", min(1.0, volatility * 8.0)

        if direction != "FLAT" and trend_strength >= self.trending_threshold and abs(momentum) >= 0.003:
            if abs(momentum) >= self.breakout_momentum_threshold and acceleration > 0:
                return "BREAKOUT", min(1.0, (abs(momentum) + volatility) * 10.0)
            return "TRENDING", min(1.0, (trend_strength + abs(momentum)) * 8.0)

        if trend_strength >= self.trending_threshold and abs(momentum) >= self.reversal_momentum_threshold:
            trend_direction = 1.0 if direction == "UP" else -1.0
            if momentum * trend_direction < 0:
                return "REVERSAL", min(1.0, (abs(momentum) + abs(acceleration)) * 10.0)

        if volatility <= self.low_volatility_threshold:
            return "LOW_VOLATILITY", min(1.0, 1.0 - (volatility / max(self.low_volatility_threshold, 1e-9)))

        if trend_strength < self.trending_threshold and volatility < self.high_volatility_threshold:
            return "RANGING", min(1.0, max(0.1, 1.0 - trend_strength - volatility))

        return "UNKNOWN", 0.2

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _stddev(values: list[float]) -> float:
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(max(0.0, variance))
