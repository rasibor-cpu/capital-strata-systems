from __future__ import annotations

from typing import List, Dict, Any


def _safe(v):
    try:
        return float(v)
    except Exception:
        return 0.0


class QuantSignalOptimizer:
    """
    Institutional-style signal optimizer.

    Combines multiple factors into a
    composite trade probability.
    """

    def __init__(self):

        self.w_score = 0.40
        self.w_pressure = 0.30
        self.w_accel = 0.20
        self.w_spread = 0.10

        self.trade_threshold = 0.55

    def normalize_spread(self, spread):

        s = abs(spread)

        if s > 40:
            return 1.0
        if s > 25:
            return 0.8
        if s > 15:
            return 0.6
        if s > 8:
            return 0.4
        return 0.2

    def optimize(self, rows: List[Dict[str, Any]]):

        optimized = []

        for row in rows:

            score = _safe(row.get("score"))
            pressure = _safe(row.get("pressure_score"))
            accel = _safe(row.get("pressure_acceleration"))
            spread = _safe(row.get("spread_bps"))

            spread_norm = self.normalize_spread(spread)

            trade_score = (
                self.w_score * score
                + self.w_pressure * pressure
                + self.w_accel * abs(accel)
                + self.w_spread * spread_norm
            )

            new_row = dict(row)

            new_row["trade_score"] = trade_score

            if trade_score >= self.trade_threshold:
                new_row["decision"] = "TRADE"
            else:
                new_row["decision"] = "IGNORE"

            optimized.append(new_row)

        return optimized