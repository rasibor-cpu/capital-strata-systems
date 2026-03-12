from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List

# Ensure the CSS project root is always importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class OpportunityScoreBreakdown:
    trend_strength: float
    liquidity_score: float
    volatility_score: float
    volume_acceleration_score: float
    spread_efficiency_score: float
    volatility_cluster_score: float
    order_flow_pressure_score: float
    liquidity_sweep_rejection_score: float
    final_score: float
    decision: str


class AIOpportunityScorer:
    """
    CSS institutional opportunity scorer.

    Engine contract:
    - score_opportunity(opportunity) -> float
    - explain_opportunity(opportunity) -> detailed dict
    """

    def __init__(
        self,
        trade_threshold: float = 0.68,
        watch_threshold: float = 0.55,
    ) -> None:
        self.trade_threshold = trade_threshold
        self.watch_threshold = watch_threshold

        self.weights: Dict[str, float] = {
            "trend_strength": 0.18,
            "liquidity_score": 0.14,
            "volatility_score": 0.12,
            "volume_acceleration_score": 0.12,
            "spread_efficiency_score": 0.10,
            "volatility_cluster_score": 0.10,
            "order_flow_pressure_score": 0.12,
            "liquidity_sweep_rejection_score": 0.12,
        }

    # --------------------------------------------------
    # PUBLIC API USED BY ENGINE
    # --------------------------------------------------

    def score_opportunity(self, opportunity: Dict[str, Any]) -> float:
        """
        Return ONLY the numeric score for engine compatibility.
        """
        breakdown = self._build_breakdown(opportunity)
        return breakdown.final_score

    def explain_opportunity(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return full explanation payload for debugging / analytics.
        """
        symbol = str(opportunity.get("symbol", "UNKNOWN"))
        breakdown = self._build_breakdown(opportunity)

        return {
            "symbol": symbol,
            "score": breakdown.final_score,
            "decision": breakdown.decision,
            "breakdown": breakdown.__dict__,
        }

    def rank_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scored: List[Dict[str, Any]] = []

        for opportunity in opportunities:
            explanation = self.explain_opportunity(opportunity)
            scored.append(explanation)

        return sorted(scored, key=lambda item: item["score"], reverse=True)

    # --------------------------------------------------
    # INTERNAL BUILD
    # --------------------------------------------------

    def _build_breakdown(self, opportunity: Dict[str, Any]) -> OpportunityScoreBreakdown:
        trend_strength = self._score_trend_strength(opportunity)
        liquidity_score = self._score_liquidity(opportunity)
        volatility_score = self._score_volatility(opportunity)
        volume_acceleration_score = self._score_volume_acceleration(opportunity)
        spread_efficiency_score = self._score_spread_efficiency(opportunity)
        volatility_cluster_score = self._score_volatility_cluster(opportunity)
        order_flow_pressure_score = self._score_order_flow_pressure(opportunity)
        liquidity_sweep_rejection_score = self._score_liquidity_sweep_rejection(opportunity)

        final_score = (
            trend_strength * self.weights["trend_strength"]
            + liquidity_score * self.weights["liquidity_score"]
            + volatility_score * self.weights["volatility_score"]
            + volume_acceleration_score * self.weights["volume_acceleration_score"]
            + spread_efficiency_score * self.weights["spread_efficiency_score"]
            + volatility_cluster_score * self.weights["volatility_cluster_score"]
            + order_flow_pressure_score * self.weights["order_flow_pressure_score"]
            + liquidity_sweep_rejection_score * self.weights["liquidity_sweep_rejection_score"]
        )

        final_score = round(_clamp(final_score), 4)

        if final_score >= self.trade_threshold:
            decision = "TRADE"
        elif final_score >= self.watch_threshold:
            decision = "WATCH"
        else:
            decision = "IGNORE"

        return OpportunityScoreBreakdown(
            trend_strength=round(trend_strength, 4),
            liquidity_score=round(liquidity_score, 4),
            volatility_score=round(volatility_score, 4),
            volume_acceleration_score=round(volume_acceleration_score, 4),
            spread_efficiency_score=round(spread_efficiency_score, 4),
            volatility_cluster_score=round(volatility_cluster_score, 4),
            order_flow_pressure_score=round(order_flow_pressure_score, 4),
            liquidity_sweep_rejection_score=round(liquidity_sweep_rejection_score, 4),
            final_score=final_score,
            decision=decision,
        )

    # --------------------------------------------------
    # FACTOR SCORERS
    # --------------------------------------------------

    def _score_trend_strength(self, opportunity: Dict[str, Any]) -> float:
        explicit = opportunity.get("trend_strength")
        if explicit is not None:
            try:
                return _clamp(float(explicit))
            except (TypeError, ValueError):
                pass

        try:
            momentum = abs(float(opportunity.get("momentum", 0.0)))
        except (TypeError, ValueError):
            momentum = 0.0

        regime = str(opportunity.get("regime", "")).upper()
        trend_efficiency = self._to_float(opportunity.get("trend_efficiency"), 0.0)

        base = _clamp(max(momentum, trend_efficiency))

        if regime == "TREND":
            base += 0.15
        elif regime == "BREAKOUT":
            base += 0.08
        elif regime in {"SIDEWAYS", "RANGE"}:
            base -= 0.05

        return _clamp(base)

    def _score_liquidity(self, opportunity: Dict[str, Any]) -> float:
        volume_24h = self._to_float(opportunity.get("volume_24h"), 0.0)
        top_of_book_depth = self._to_float(opportunity.get("top_of_book_depth"), 0.0)
        slippage_bps = self._to_float(opportunity.get("slippage_bps"), 10.0)

        if volume_24h >= 50_000_000:
            volume_score = 1.0
        elif volume_24h >= 10_000_000:
            volume_score = 0.85
        elif volume_24h >= 2_500_000:
            volume_score = 0.65
        elif volume_24h >= 500_000:
            volume_score = 0.45
        elif volume_24h > 0:
            volume_score = 0.30
        else:
            volume_score = 0.20

        if top_of_book_depth >= 500_000:
            depth_score = 1.0
        elif top_of_book_depth >= 100_000:
            depth_score = 0.80
        elif top_of_book_depth >= 25_000:
            depth_score = 0.60
        elif top_of_book_depth > 0:
            depth_score = 0.35
        else:
            depth_score = 0.20

        if slippage_bps <= 1:
            slippage_score = 1.0
        elif slippage_bps <= 3:
            slippage_score = 0.85
        elif slippage_bps <= 7:
            slippage_score = 0.60
        elif slippage_bps <= 12:
            slippage_score = 0.35
        else:
            slippage_score = 0.15

        return _clamp((volume_score * 0.45) + (depth_score * 0.35) + (slippage_score * 0.20))

    def _score_volatility(self, opportunity: Dict[str, Any]) -> float:
        volatility = self._to_float(opportunity.get("volatility"), 0.0)
        avg_volatility = self._to_float(opportunity.get("avg_volatility"), 0.0)
        regime = str(opportunity.get("regime", "")).upper()

        ratio = volatility / avg_volatility if avg_volatility > 0 else volatility

        if ratio <= 0.5:
            score = 0.25
        elif ratio <= 0.8:
            score = 0.50
        elif ratio <= 1.2:
            score = 0.85
        elif ratio <= 1.8:
            score = 1.00
        elif ratio <= 2.5:
            score = 0.72
        else:
            score = 0.45

        if regime == "BREAKOUT":
            score += 0.05
        if regime in {"SIDEWAYS", "RANGE"} and ratio > 1.8:
            score -= 0.10

        return _clamp(score)

    def _score_volume_acceleration(self, opportunity: Dict[str, Any]) -> float:
        volume_24h = self._to_float(opportunity.get("volume_24h"), 0.0)
        avg_volume_24h = self._to_float(opportunity.get("avg_volume_24h"), 0.0)

        if avg_volume_24h <= 0:
            return 0.50 if volume_24h > 0 else 0.0

        ratio = volume_24h / avg_volume_24h

        if ratio <= 0.7:
            return 0.20
        if ratio <= 1.0:
            return 0.45
        if ratio <= 1.3:
            return 0.68
        if ratio <= 1.8:
            return 0.85
        if ratio <= 2.5:
            return 1.00
        if ratio <= 4.0:
            return 0.90
        return 0.75

    def _score_spread_efficiency(self, opportunity: Dict[str, Any]) -> float:
        spread_bps = self._to_float(opportunity.get("spread_bps"), 999.0)

        if spread_bps <= 1:
            return 1.00
        if spread_bps <= 3:
            return 0.90
        if spread_bps <= 5:
            return 0.78
        if spread_bps <= 10:
            return 0.55
        if spread_bps <= 20:
            return 0.30
        return 0.10

    def _score_volatility_cluster(self, opportunity: Dict[str, Any]) -> float:
        volatility = self._to_float(opportunity.get("volatility"), 0.0)
        avg_volatility = self._to_float(opportunity.get("avg_volatility"), 0.0)
        regime = str(opportunity.get("regime", "")).upper()

        ratio = volatility / avg_volatility if avg_volatility > 0 else volatility

        if 0.9 <= ratio <= 1.6:
            score = 1.0
        elif 0.7 <= ratio < 0.9:
            score = 0.75
        elif 1.6 < ratio <= 2.2:
            score = 0.72
        elif 0.5 <= ratio < 0.7:
            score = 0.45
        else:
            score = 0.25

        if regime == "TREND" and 1.0 <= ratio <= 1.8:
            score += 0.05

        return _clamp(score)

    def _score_order_flow_pressure(self, opportunity: Dict[str, Any]) -> float:
        order_flow_delta = self._to_float(opportunity.get("order_flow_delta"), 0.0)
        buy_pressure = self._to_float(opportunity.get("buy_pressure"), 0.0)
        sell_pressure = self._to_float(opportunity.get("sell_pressure"), 0.0)
        regime = str(opportunity.get("regime", "")).upper()

        total_pressure = buy_pressure + sell_pressure
        pressure_bias = ((buy_pressure - sell_pressure) / total_pressure) if total_pressure > 0 else 0.0
        composite = (0.6 * order_flow_delta) + (0.4 * pressure_bias)

        if composite <= -0.60:
            score = 0.10
        elif composite <= -0.25:
            score = 0.28
        elif composite < 0.10:
            score = 0.50
        elif composite < 0.30:
            score = 0.70
        elif composite < 0.55:
            score = 0.88
        else:
            score = 1.00

        if regime == "BREAKOUT" and composite > 0.20:
            score += 0.05

        return _clamp(score)

    def _score_liquidity_sweep_rejection(self, opportunity: Dict[str, Any]) -> float:
        liquidity_sweep_flag = bool(opportunity.get("liquidity_sweep_flag", False))
        rejection_strength = self._to_float(opportunity.get("rejection_strength"), 0.0)
        wick_reversal_strength = self._to_float(opportunity.get("wick_reversal_strength"), 0.0)
        current_price = self._to_float(
            opportunity.get("current_price", opportunity.get("price")),
            0.0,
        )
        recent_high = self._to_float(opportunity.get("recent_high"), 0.0)
        recent_low = self._to_float(opportunity.get("recent_low"), 0.0)

        proximity_score = 0.0
        if current_price > 0 and recent_high > 0 and recent_low > 0 and recent_high > recent_low:
            range_size = recent_high - recent_low
            if range_size > 0:
                distance_to_high = abs(recent_high - current_price) / range_size
                distance_to_low = abs(current_price - recent_low) / range_size
                proximity = 1.0 - min(distance_to_high, distance_to_low)
                proximity_score = _clamp(proximity)

        base = 0.15
        if liquidity_sweep_flag:
            base += 0.35

        base += 0.25 * _clamp(rejection_strength)
        base += 0.15 * _clamp(wick_reversal_strength)
        base += 0.10 * proximity_score

        return _clamp(base)

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default


if __name__ == "__main__":
    scorer = AIOpportunityScorer()

    sample_opportunity = {
        "symbol": "BTC-USD",
        "price": 68250.0,
        "current_price": 68250.0,
        "spread_bps": 2.2,
        "volume_24h": 32500000.0,
        "avg_volume_24h": 18000000.0,
        "volatility": 1.45,
        "avg_volatility": 1.10,
        "regime": "TREND",
        "momentum": 0.72,
        "trend_efficiency": 0.66,
        "order_flow_delta": 0.44,
        "buy_pressure": 61.0,
        "sell_pressure": 39.0,
        "recent_high": 68900.0,
        "recent_low": 66800.0,
        "rejection_strength": 0.70,
        "wick_reversal_strength": 0.66,
        "liquidity_sweep_flag": True,
        "top_of_book_depth": 250000.0,
        "slippage_bps": 2.0,
    }

    print("Numeric score:", scorer.score_opportunity(sample_opportunity))
    print("Detailed explanation:", scorer.explain_opportunity(sample_opportunity))