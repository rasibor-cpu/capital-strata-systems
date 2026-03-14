from __future__ import annotations

from typing import Any, Dict, List


class QuantSignalOptimizer:
    """
    CSS Quant Signal Optimizer

    Converts upstream intelligence output into execution decisions.

    Decision states:
    - TRADE
    - WATCH
    - IGNORE

    Calibrated to the score ranges currently being produced by the live CSS stack.
    """

    def __init__(self) -> None:
        self.trade_threshold = 0.18
        self.watch_threshold = 0.10

    def _safe(self, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def optimize(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        optimized: List[Dict[str, Any]] = []

        for row in rows:
            symbol = str(row.get("symbol", "")).upper()
            score = self._safe(row.get("score", 0.0))
            pressure = self._safe(row.get("pressure_score", 0.0))
            accel = self._safe(row.get("pressure_acceleration", 0.0))
            spread = abs(self._safe(row.get("spread_bps", 0.0)))
            regime = str(row.get("regime", "NEUTRAL")).upper()

            trade_score = (
                score * 0.55
                + pressure * 0.30
                + accel * 0.15
            )

            if spread > 5:
                trade_score += 0.02
            if spread > 15:
                trade_score += 0.03
            if spread > 30:
                trade_score += 0.05

            if "RANGE" in regime or "MEAN" in regime or "NEUTRAL" in regime:
                trade_score += 0.01
            elif "DEFENSIVE" in regime or "PANIC" in regime:
                trade_score -= 0.03

            if trade_score < 0.0:
                trade_score = 0.0
            if trade_score > 1.0:
                trade_score = 1.0

            if trade_score >= self.trade_threshold:
                decision = "TRADE"
            elif trade_score >= self.watch_threshold:
                decision = "WATCH"
            else:
                decision = "IGNORE"

            enriched = dict(row)
            enriched["symbol"] = symbol
            enriched["trade_score"] = trade_score
            enriched["decision"] = decision

            print(
                f"[{decision}] {symbol}: "
                f"score={score:.6f}, "
                f"pressure={pressure:.6f}, "
                f"accel={accel:.6f}, "
                f"spread={spread:.6f}, "
                f"trade_score={trade_score:.6f}, "
                f"regime={regime}"
            )

            optimized.append(enriched)

        return optimized