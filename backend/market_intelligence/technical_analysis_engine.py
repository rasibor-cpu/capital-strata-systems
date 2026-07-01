from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class TechnicalAnalysisEngine:
    """Deterministic advisory-only technical analysis from internal price data."""

    def analyze(
        self,
        *,
        price_history: Sequence[Any] | None = None,
        returns: Sequence[Any] | None = None,
        volatility: Any = None,
        trend_data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        prices = self._numbers(price_history)
        ret = self._numbers(returns)
        trend = trend_data if isinstance(trend_data, Mapping) else {}
        reasons: list[str] = []

        if len(prices) < 2 and not ret and not trend:
            return self._unavailable("technical_inputs_unavailable")

        status = "OK" if len(prices) >= 5 or len(ret) >= 5 else "PARTIAL"
        if status == "PARTIAL":
            reasons.append("limited_technical_history")

        short_ma = self._avg(prices[-5:]) if len(prices) >= 5 else self._avg(prices)
        long_ma = self._avg(prices[-20:]) if len(prices) >= 20 else self._avg(prices)
        momentum = self._momentum(prices, ret)
        vol = self._safe_float(volatility, self._std(ret) if ret else 0.0)
        rsi_score = self._rsi_score(prices)
        breakout = self._breakout_status(prices)
        trend_strength = min(100.0, abs(momentum) * 5000.0 + abs(short_ma - long_ma) / max(abs(long_ma), 1.0) * 1000.0)
        trend_bias = 0.0 if long_ma == 0 else (short_ma - long_ma) / abs(long_ma)

        score = 50.0
        score += max(-25.0, min(25.0, momentum * 2500.0))
        score += max(-15.0, min(15.0, trend_bias * 1000.0))
        if rsi_score is not None:
            score += max(-10.0, min(10.0, (rsi_score - 50.0) / 3.0))
        if breakout == "BREAKOUT_UP":
            score += 10.0
        elif breakout == "BREAKOUT_DOWN":
            score -= 10.0
        if vol > 0.08:
            score -= 8.0

        bounded = self._bounded(score)
        signal = "BULLISH" if bounded >= 65 else "BEARISH" if bounded <= 35 else "NEUTRAL"
        if signal == "BULLISH":
            reasons.append("technical_momentum_positive")
        elif signal == "BEARISH":
            reasons.append("technical_momentum_negative")
        else:
            reasons.append("technical_signal_neutral")

        return {
            "status": status,
            "technical_score": bounded,
            "technical_signal": signal,
            "moving_average_trend": "UP" if short_ma > long_ma else "DOWN" if short_ma < long_ma else "FLAT",
            "momentum": round(momentum, 8),
            "volatility_regime": "HIGH" if vol > 0.08 else "MEDIUM" if vol > 0.03 else "LOW",
            "rsi_score": round(rsi_score, 6) if rsi_score is not None else None,
            "breakout_status": breakout,
            "trend_strength": round(trend_strength, 6),
            "reasons": sorted(set(reasons)),
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _numbers(values: Sequence[Any] | None) -> list[float]:
        result: list[float] = []
        for value in values or []:
            try:
                result.append(float(value))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @classmethod
    def _std(cls, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = cls._avg(values)
        return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5

    @staticmethod
    def _momentum(prices: list[float], returns: list[float]) -> float:
        if len(prices) >= 2 and prices[0] != 0:
            return (prices[-1] - prices[0]) / abs(prices[0])
        return sum(returns) / len(returns) if returns else 0.0

    @classmethod
    def _rsi_score(cls, prices: list[float]) -> float | None:
        if len(prices) < 15:
            return None
        gains: list[float] = []
        losses: list[float] = []
        for previous, current in zip(prices[-15:-1], prices[-14:]):
            change = current - previous
            if change >= 0:
                gains.append(change)
            else:
                losses.append(abs(change))
        avg_gain = cls._avg(gains) if gains else 0.0
        avg_loss = cls._avg(losses) if losses else 0.0
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _breakout_status(prices: list[float]) -> str:
        if len(prices) < 5:
            return "UNKNOWN"
        previous = prices[:-1]
        if prices[-1] > max(previous):
            return "BREAKOUT_UP"
        if prices[-1] < min(previous):
            return "BREAKOUT_DOWN"
        spread = max(prices[-5:]) - min(prices[-5:])
        base = max(abs(prices[-1]), 1.0)
        return "CONSOLIDATION" if spread / base < 0.02 else "RANGE"

    @staticmethod
    def _bounded(value: float) -> int:
        return max(0, min(100, int(round(value))))

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "technical_score": 0,
            "technical_signal": "DATA_UNAVAILABLE",
            "reasons": [reason],
            "advisory_only": True,
            "execution_allowed": False,
        }
