from __future__ import annotations

from typing import Any, Dict, List

from backend.intelligence.market_regime_detector import MarketRegimeDetector


class TradeDecisionEngine:
    """
    CSS Trade Decision Engine

    Purpose:
    - apply final intelligence/confluence checks before trade execution
    - use regime classification to determine whether a BUY signal should proceed
    - provide stable, backward-compatible output for the live dashboard

    Output contract:
    {
        "execute_trade": bool,
        "regime": str,
        "regime_reason": str,
        "confluence_score": float,
    }
    """

    def __init__(self) -> None:
        self.regime_detector = MarketRegimeDetector()

        # Regime-specific execution thresholds
        self.mean_reversion_threshold = 0.35
        self.trend_threshold = 0.55
        self.breakout_threshold = 0.70

    def evaluate_trade(self, asset: str, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles or len(candles) < 20:
            return {
                "execute_trade": False,
                "regime": "UNSTABLE",
                "regime_reason": "insufficient candle history",
                "confluence_score": 0.0,
            }

        regime_info = self.regime_detector.detect_regime(candles)
        regime = str(regime_info.get("regime", "UNSTABLE")).upper()
        regime_reason = str(regime_info.get("reason", "unknown"))
        regime_confidence = float(regime_info.get("confidence", 0.0))

        confluence_score = self._compute_confluence(candles, regime_confidence)

        if regime == "MEAN_REVERSION":
            execute_trade = confluence_score >= self.mean_reversion_threshold
        elif regime == "TREND":
            execute_trade = confluence_score >= self.trend_threshold
        elif regime == "BREAKOUT":
            execute_trade = confluence_score >= self.breakout_threshold
        else:
            execute_trade = False

        return {
            "execute_trade": execute_trade,
            "regime": regime,
            "regime_reason": regime_reason,
            "confluence_score": round(confluence_score, 2),
        }

    def _compute_confluence(self, candles: List[Dict[str, Any]], regime_confidence: float) -> float:
        closes = [self._to_float(c.get("close"), 0.0) for c in candles]
        highs = [self._to_float(c.get("high"), 0.0) for c in candles]
        lows = [self._to_float(c.get("low"), 0.0) for c in candles]

        if len(closes) < 20:
            return 0.0

        last = closes[-1]
        mean_5 = sum(closes[-5:]) / 5.0
        mean_20 = sum(closes[-20:]) / 20.0

        # Distance of last price from recent average
        mean_reversion_component = 0.0
        if mean_20 > 0:
            deviation = abs(last - mean_20) / mean_20
            mean_reversion_component = min(deviation * 8.0, 0.35)

        # Short-term momentum / follow-through
        momentum_component = 0.0
        if mean_5 > 0 and mean_20 > 0:
            slope = abs(mean_5 - mean_20) / mean_20
            momentum_component = min(slope * 10.0, 0.20)

        # Candle range stability / volatility sanity check
        range_component = 0.0
        recent_ranges = []
        for h, l, c in zip(highs[-10:], lows[-10:], closes[-10:]):
            if c > 0:
                recent_ranges.append(abs(h - l) / c)

        if recent_ranges:
            avg_range = sum(recent_ranges) / len(recent_ranges)
            if avg_range <= 0.01:
                range_component = 0.20
            elif avg_range <= 0.02:
                range_component = 0.12
            elif avg_range <= 0.03:
                range_component = 0.06
            else:
                range_component = 0.0

        confidence_component = min(max(regime_confidence, 0.0), 1.0) * 0.25

        score = (
            mean_reversion_component
            + momentum_component
            + range_component
            + confidence_component
        )

        return max(0.0, min(score, 0.99))

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default