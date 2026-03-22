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
    - orchestrator compatible
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
    # ORCHESTRATOR INTERFACE
    # ------------------------------------------------

    def compute_acceleration(
        self,
        asset: str | None = None,
        candles: List[Dict[str, Any]] | None = None,
        pressure_score: float | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Orchestrator-facing interface.

        Supports:
        - direct pressure_score input
        - asset/symbol identity
        - optional candles fallback
        """

        symbol = str(
            asset
            or kwargs.get("symbol")
            or kwargs.get("asset")
            or "UNKNOWN"
        ).upper()

        current_pressure = 0.0

        if pressure_score is not None:
            current_pressure = _safe_float(pressure_score, 0.0)
        else:
            current_pressure = self._infer_pressure_from_inputs(
                candles=candles or [],
                **kwargs,
            )

        history = self.pressure_history.setdefault(
            symbol,
            deque(maxlen=self.max_history),
        )
        history.append(current_pressure)

        acceleration_score = self._compute_acceleration_score(list(history))

        stage = (
            "SURGING" if acceleration_score >= 0.65 else
            "BUILDING" if acceleration_score >= 0.35 else
            "EARLY" if acceleration_score >= 0.12 else
            "NONE"
        )

        return {
            "score": round(acceleration_score, 4),
            "acceleration_score": round(acceleration_score, 4),
            "stage": stage,
            "pressure_score": round(current_pressure, 4),
        }

    # ------------------------------------------------
    # CORE PROCESSOR
    # ------------------------------------------------

    def _process_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            symbol = str(
                row.get("symbol")
                or row.get("asset")
                or ""
            ).upper()

            current_pressure = _safe_float(row.get("pressure_score"), 0.0)

            history = self.pressure_history.setdefault(
                symbol,
                deque(maxlen=self.max_history),
            )
            history.append(current_pressure)

            acceleration_score = self._compute_acceleration_score(list(history))

            new_row = dict(row)
            new_row["pressure_acceleration"] = round(acceleration_score, 4)
            new_row["acceleration_score"] = round(acceleration_score, 4)

            if acceleration_score >= 0.65:
                new_row["acceleration_stage"] = "SURGING"
            elif acceleration_score >= 0.35:
                new_row["acceleration_stage"] = "BUILDING"
            elif acceleration_score >= 0.12:
                new_row["acceleration_stage"] = "EARLY"
            else:
                new_row["acceleration_stage"] = "NONE"

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

        velocity_component = max(0.0, velocity) * 3.0
        acceleration_component = max(0.0, acceleration) * 4.0
        pressure_context_component = latest * 0.20

        raw_score = (
            velocity_component
            + acceleration_component
            + pressure_context_component
        )

        return _clamp01(raw_score)

    # ------------------------------------------------
    # SAFE FALLBACK INFERENCE
    # ------------------------------------------------

    def _infer_pressure_from_inputs(
        self,
        candles: List[Dict[str, Any]] | List[Any],
        **kwargs: Any,
    ) -> float:
        """
        Fallback path when orchestrator calls this engine without
        providing an explicit pressure_score.

        Priority:
        1. direct pressure-like fields from kwargs
        2. simple candle-derived proxy
        """

        for key in (
            "pressure_score",
            "pressure",
            "current_pressure",
            "opportunity_pressure",
        ):
            if key in kwargs:
                return _clamp01(_safe_float(kwargs.get(key), 0.0))

        if not candles or len(candles) < 2:
            return 0.0

        try:
            last = candles[-1]
            prev = candles[-2]

            last_close = self._extract_close(last)
            prev_close = self._extract_close(prev)
            last_high = self._extract_high(last)
            last_low = self._extract_low(last)

            if last_close <= 0 or prev_close <= 0:
                return 0.0

            move = abs(last_close - prev_close) / prev_close
            intrabar_range = abs(last_high - last_low) / last_close if last_close > 0 else 0.0

            proxy_pressure = (move * 8.0) + (intrabar_range * 6.0)
            return _clamp01(proxy_pressure)
        except Exception:
            return 0.0

    def _extract_close(self, candle: Any) -> float:
        if isinstance(candle, dict):
            return _safe_float(candle.get("close"), 0.0)
        if hasattr(candle, "close"):
            return _safe_float(getattr(candle, "close"), 0.0)
        if isinstance(candle, (list, tuple)) and len(candle) > 4:
            return _safe_float(candle[4], 0.0)
        return 0.0

    def _extract_high(self, candle: Any) -> float:
        if isinstance(candle, dict):
            return _safe_float(candle.get("high"), 0.0)
        if hasattr(candle, "high"):
            return _safe_float(getattr(candle, "high"), 0.0)
        if isinstance(candle, (list, tuple)) and len(candle) > 2:
            return _safe_float(candle[2], 0.0)
        return 0.0

    def _extract_low(self, candle: Any) -> float:
        if isinstance(candle, dict):
            return _safe_float(candle.get("low"), 0.0)
        if hasattr(candle, "low"):
            return _safe_float(getattr(candle, "low"), 0.0)
        if isinstance(candle, (list, tuple)) and len(candle) > 3:
            return _safe_float(candle[3], 0.0)
        return 0.0