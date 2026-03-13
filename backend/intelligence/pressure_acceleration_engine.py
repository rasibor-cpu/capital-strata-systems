from __future__ import annotations

from typing import Dict, List, Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


class PressureAccelerationEngine:
    """
    Detects when pressure is increasing rapidly.

    This is a strong signal that a reversal
    or breakout may be imminent.
    """

    def __init__(self):
        self.previous_pressure: Dict[str, float] = {}

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        enriched: List[Dict[str, Any]] = []

        for row in rows:

            symbol = str(row.get("symbol", ""))

            current_pressure = _safe_float(row.get("pressure_score"))

            prev = self.previous_pressure.get(symbol, current_pressure)

            acceleration = current_pressure - prev

            self.previous_pressure[symbol] = current_pressure

            new_row = dict(row)
            new_row["pressure_acceleration"] = acceleration

            enriched.append(new_row)

        return enriched