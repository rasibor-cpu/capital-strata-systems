from __future__ import annotations

from typing import Dict, List, Any


class OpportunityMomentumWindowEngine:
    """
    Detects early momentum windows before reversals.

    Signals when:
    - VWAP distance begins compressing
    - pressure score rising
    - acceleration starting
    - trend slope flattening
    """

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        enriched: List[Dict[str, Any]] = []

        for r in rows:

            price = float(r.get("price", 0))
            vwap = float(r.get("vwap", 0))

            pressure = float(r.get("pressure_score", 0))
            accel = float(r.get("pressure_acceleration", 0))

            trend = float(r.get("trend", 0))
            spread = float(r.get("spread_bps", 0))

            vwap_dist = 0.0
            if vwap > 0:
                vwap_dist = (price - vwap) / vwap

            # --- momentum window score ---
            score = (
                abs(vwap_dist) * 1.2
                + pressure * 0.9
                + accel * 1.1
                + abs(trend) * 0.6
            )

            # normalize
            momentum_score = min(score, 1.0)

            # window trigger condition
            trigger = (
                pressure > 0.45
                and accel > 0.02
                and abs(vwap_dist) < 0.03
            )

            new_row = dict(r)
            new_row["momentum_score"] = momentum_score
            new_row["momentum_window_trigger"] = trigger

            enriched.append(new_row)

        return enriched