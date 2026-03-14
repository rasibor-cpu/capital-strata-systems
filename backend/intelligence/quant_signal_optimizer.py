from __future__ import annotations

from typing import Any, Dict, List


class QuantSignalOptimizer:
    """
    CSS Quant Signal Optimizer

    Purpose:
    - Convert upstream intelligence output into execution-ready decisions
    - Preserve a conservative risk posture while allowing live paper-trade flow
    - Produce three decision states:
        TRADE
        WATCH
        IGNORE

    Notes:
    - Upstream scores may arrive on different scales depending on module state
    - This optimizer therefore normalizes inputs defensively
    - Thresholds are intentionally moderate so CSS can begin generating trades
      for real-world testing instead of remaining permanently silent
    """

    def __init__(
        self,
        *,
        trade_threshold: float = 0.22,
        watch_threshold: float = 0.12,
        min_score_floor: float = 0.03,
    ) -> None:
        self.trade_threshold = float(trade_threshold)
        self.watch_threshold = float(watch_threshold)
        self.min_score_floor = float(min_score_floor)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _clamp(self, value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, float(value)))

    def _normalize_component(self, value: float) -> float:
        """
        Defensive normalization for mixed upstream scales.

        Expected behavior:
        - Negative values are treated as 0
        - 0..1 values remain unchanged
        - Values above 1 are compressed into the 0..1 band
        """
        value = self._safe_float(value, 0.0)

        if value <= 0:
            return 0.0

        if value <= 1.0:
            return value

        # Gentle compression for oversized values
        compressed = value / (1.0 + value)
        return self._clamp(compressed)

    def optimize(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        optimized: List[Dict[str, Any]] = []

        for row in rows:
            symbol = str(row.get("symbol", "")).upper()

            raw_score = self._safe_float(row.get("score", 0.0), 0.0)
            raw_pressure = self._safe_float(row.get("pressure_score", 0.0), 0.0)
            raw_accel = self._safe_float(row.get("pressure_acceleration", 0.0), 0.0)
            spread_bps = self._safe_float(row.get("spread_bps", 0.0), 0.0)
            regime = str(row.get("regime", "NEUTRAL")).upper()

            score = self._normalize_component(raw_score)
            pressure = self._normalize_component(raw_pressure)
            accel = self._normalize_component(raw_accel)

            # Moderate spread encouragement: some dislocation is useful for mean reversion
            abs_spread = abs(spread_bps)
            spread_bonus = 0.0
            if abs_spread >= 5:
                spread_bonus = 0.03
            if abs_spread >= 10:
                spread_bonus = 0.05
            if abs_spread >= 20:
                spread_bonus = 0.07

            # Regime weighting
            regime_bonus = 0.0
            if "MEAN" in regime or "RANGE" in regime or "NEUTRAL" in regime:
                regime_bonus = 0.03
            elif "TREND" in regime:
                regime_bonus = -0.01
            elif "DEFENSIVE" in regime or "PANIC" in regime:
                regime_bonus = -0.05

            trade_score = (
                score * 0.50
                + pressure * 0.30
                + accel * 0.20
                + spread_bonus
                + regime_bonus
            )

            trade_score = round(self._clamp(trade_score, 0.0, 1.0), 6)

            # Hard block: if absolutely everything is tiny, ignore it
            if max(score, pressure, accel) < self.min_score_floor:
                decision = "IGNORE"
            elif trade_score >= self.trade_threshold:
                decision = "TRADE"
            elif trade_score >= self.watch_threshold:
                decision = "WATCH"
            else:
                decision = "IGNORE"

            enriched = dict(row)
            enriched["symbol"] = symbol
            enriched["score"] = score
            enriched["pressure_score"] = pressure
            enriched["pressure_acceleration"] = accel
            enriched["spread_bps"] = spread_bps
            enriched["regime"] = regime
            enriched["trade_score"] = trade_score
            enriched["decision"] = decision

            print(
                f"[{decision}] {symbol}: "
                f"score={score:.6f}, "
                f"pressure={pressure:.6f}, "
                f"accel={accel:.6f}, "
                f"spread={spread_bps:.6f}, "
                f"trade_score={trade_score:.6f}, "
                f"regime={regime}"
            )

            optimized.append(enriched)

        return optimized