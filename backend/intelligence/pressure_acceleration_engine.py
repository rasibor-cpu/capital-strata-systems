from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class PressureAccelerationEngine:
    """
    CSS Pressure Acceleration Engine

    Detects when pressure is increasing rapidly enough
    to suggest an imminent reversal or breakout.

    Design goals:
    - row-pipeline compatible
    - stable across live cycles
    - normalized output for optimizer consumption
    """

    def __init__(self) -> None:
        self.pressure_history: Dict[str, Deque[float]] = {}
        self.max_history = 4

    # ------------------------------------------------
    # CSS STANDARD ROW INTERFACE
    # ------------------------------------------------

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._process_rows(rows)

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._process_rows(rows)

    # ------------------------------------------------
    # CORE PROCESSOR
    # ------------------------------------------------

    def _process_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            symbol = str(row.get("symbol", "")).upper()
            current_pressure = _safe_float(row.get("pressure_score"), 0.0)

            history = self.pressure_history.setdefault(
                symbol,
                deque(maxlen=self.max_history),
            )
            history.append(current_pressure)

            acceleration_score = self._compute_acceleration_score(list(history))

            new_row = dict(row)
            new_row["pressure_acceleration"] = round(acceleration_score, 4)

            enriched.append(new_row)

        return enriched

    # ------------------------------------------------
    # ACCELERATION LOGIC
    # ------------------------------------------------

    def _compute_acceleration_score(self, history: List[float]) -> float:
        """
        Converts recent pressure history into a normalized 0..1 score.

        Uses:
        - velocity: latest pressure increase
        - acceleration: change in velocity
        - absolute pressure context: strong current pressure matters
        """

        if len(history) < 2:
            return 0.0

        latest = history[-1]
        prev = history[-2]
        velocity = latest - prev

        if len(history) < 3:
            raw_score = max(0.0, velocity) * 3.0 + latest * 0.20
            return _clamp01(raw_score)

        prev2 = history[-3]
        prev_velocity = prev - prev2
        acceleration = velocity - prev_velocity

        # Positive-only bias for entry timing
        velocity_component = max(0.0, velocity) * 3.0
        acceleration_component = max(0.0, acceleration) * 4.0
        pressure_context_component = latest * 0.20

        raw_score = (
            velocity_component
            + acceleration_component
            + pressure_context_component
        )

        return _clamp01(raw_score)