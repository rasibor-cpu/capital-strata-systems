from __future__ import annotations

import math
from typing import Any, Mapping


class LiquidityIntelligenceEngineError(RuntimeError):
    """Fail-closed exception for liquidity intelligence."""


class LiquidityIntelligenceEngine:
    """Liquidity intelligence scorer with fail-closed rejection."""

    def score(self, *, instrument: Mapping[str, Any], market_snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(instrument, Mapping):
            raise LiquidityIntelligenceEngineError("instrument must be a mapping")
        if not isinstance(market_snapshot, Mapping):
            raise LiquidityIntelligenceEngineError("market_snapshot must be a mapping")

        candles = list(market_snapshot.get("candles") or [])
        if not candles:
            raise LiquidityIntelligenceEngineError("market_snapshot.candles must not be empty")

        tick = max(0.000001, float(instrument.get("tick_size", 0.01) or 0.01))
        min_order_size = max(0.0001, float(instrument.get("min_order_size", 1.0) or 1.0))
        max_order_size = max(min_order_size, float(instrument.get("max_order_size", min_order_size) or min_order_size))

        close = float(candles[-1].get("close", 0.0) or 0.0)
        if close <= 0:
            raise LiquidityIntelligenceEngineError("last close must be positive")

        volumes = [max(0.0, float(row.get("volume", 0.0) or 0.0)) for row in candles]
        volume = volumes[-1]
        average_volume = sum(volumes) / len(volumes)

        spread = min(0.2, max(0.00001, (tick / close) * 5.0))
        order_book_depth = max(0.0, min(1.0, (max_order_size / max(min_order_size, 1.0)) / 1000.0))
        slippage_estimate = min(0.25, max(0.0001, spread * (1.0 + max(0.0, 1.0 - (volume / max(average_volume, 1.0))))))

        spread_score = max(0.0, min(1.0, 1.0 - (spread / 0.02)))
        volume_score = max(0.0, min(1.0, math.log10(max(volume, 1.0)) / 6.0))
        avg_volume_score = max(0.0, min(1.0, math.log10(max(average_volume, 1.0)) / 6.0))
        slippage_score = max(0.0, min(1.0, 1.0 - (slippage_estimate / 0.04)))

        liquidity_score = max(0.0, min(1.0, (spread_score * 0.30) + (volume_score * 0.20) + (avg_volume_score * 0.20) + (order_book_depth * 0.15) + (slippage_score * 0.15)))

        if liquidity_score >= 0.75:
            liquidity_rating = "A"
        elif liquidity_score >= 0.55:
            liquidity_rating = "B"
        elif liquidity_score >= 0.35:
            liquidity_rating = "C"
        else:
            liquidity_rating = "D"

        return {
            "spread": round(spread, 8),
            "volume": round(volume, 8),
            "average_volume": round(average_volume, 8),
            "order_book_depth": round(order_book_depth, 8),
            "slippage_estimate": round(slippage_estimate, 8),
            "liquidity_rating": liquidity_rating,
            "liquidity_score": round(liquidity_score, 8),
            "eligible": liquidity_score >= 0.35,
            "decision_hint": "ALLOW" if liquidity_score >= 0.35 else "REJECT",
        }
