from __future__ import annotations


class QuantSignalOptimizer:
    """
    CSS Quant Signal Optimizer

    Converts AI opportunity scores into actionable decisions.

    Decisions:
        TRADE
        WATCH
        IGNORE
    """

    def __init__(self):

        # Conservative defaults (can tune later)

        self.trade_threshold = 0.35
        self.watch_threshold = 0.20

    def optimize(self, rows):

        optimized = []

        for r in rows:

            score = float(r.get("score", 0))
            pressure = float(r.get("pressure_score", 0))
            accel = float(r.get("pressure_acceleration", 0))

            # composite trade score

            trade_score = (
                score * 0.5
                + pressure * 0.3
                + accel * 0.2
            )

            if trade_score >= self.trade_threshold:

                decision = "TRADE"

            elif trade_score >= self.watch_threshold:

                decision = "WATCH"

            else:

                decision = "IGNORE"

            r["trade_score"] = trade_score
            r["decision"] = decision

            optimized.append(r)

        return optimized