from __future__ import annotations

from typing import List, Dict, Any


class OpportunityPressureMapEngine:
    """
    CSS Opportunity Pressure Map Engine

    This engine builds a market-wide pressure map across all scanned assets.

    It identifies:

    • clustered opportunity pressure
    • ranked pressure assets
    • market pressure index
    • relative pressure acceleration

    These signals help the optimizer detect when the market
    is entering a coordinated opportunity phase.
    """

    def __init__(self):

        self.last_market_pressure = 0.0

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        if not rows:
            return rows

        pressures = []

        for r in rows:

            p = float(r.get("pressure_score", 0.0))
            a = float(r.get("pressure_acceleration", 0.0))

            combined = (p * 0.7) + (a * 0.3)

            r["pressure_combined"] = combined

            pressures.append(combined)

        pressures_sorted = sorted(pressures, reverse=True)

        max_pressure = pressures_sorted[0] if pressures_sorted else 0

        market_pressure_index = sum(pressures) / len(pressures)

        for r in rows:

            p = r["pressure_combined"]

            # relative rank
            rank = pressures_sorted.index(p) + 1

            r["pressure_rank"] = rank

            # cluster detection
            if p > market_pressure_index * 1.25:
                r["pressure_cluster"] = 1
            else:
                r["pressure_cluster"] = 0

            # normalized pressure
            if max_pressure > 0:
                r["pressure_relative"] = p / max_pressure
            else:
                r["pressure_relative"] = 0

            r["market_pressure_index"] = market_pressure_index

        self.last_market_pressure = market_pressure_index

        return rows