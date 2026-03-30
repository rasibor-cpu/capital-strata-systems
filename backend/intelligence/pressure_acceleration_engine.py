from __future__ import annotations

from typing import Any, Dict, List


class PressureAccelerationEngine:
    """
    Computes pressure acceleration safely from row-based market data.

    Expected input row keys may include:
    - pressure_score
    - buy_pressure
    - sell_pressure
    - momentum
    - velocity
    - price
    - current_price
    - vwap

    Outputs added per row:
    - pressure_acceleration
    - acceleration_score
    """

    def __init__(self) -> None:
        self._prev_pressure_by_symbol: Dict[str, float] = {}

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _clamp01(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _derive_pressure(self, row: Dict[str, Any]) -> float:
        explicit_pressure = row.get("pressure_score")
        if explicit_pressure is not None:
            return self._safe_float(explicit_pressure, 0.0)

        buy_pressure = self._safe_float(row.get("buy_pressure"), 0.0)
        sell_pressure = self._safe_float(row.get("sell_pressure"), 0.0)
        momentum = self._safe_float(row.get("momentum"), 0.0)
        velocity = self._safe_float(row.get("velocity"), 0.0)

        price = self._safe_float(row.get("price"), 0.0)
        current_price = self._safe_float(row.get("current_price"), price)
        vwap = self._safe_float(row.get("vwap"), current_price)

        vwap_dev = 0.0
        if vwap > 0:
            vwap_dev = abs((current_price - vwap) / (vwap + 1e-9))

        derived = (
            abs(buy_pressure - sell_pressure) * 0.35
            + abs(momentum) * 18.0 * 0.30
            + abs(velocity) * 18.0 * 0.20
            + vwap_dev * 25.0 * 0.15
        )

        return self._clamp01(derived)

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows or []:
            if not isinstance(row, dict):
                continue

            out = dict(row)

            symbol = str(out.get("symbol") or out.get("asset") or "")
            current_pressure = self._derive_pressure(out)

            previous_pressure = self._prev_pressure_by_symbol.get(symbol, current_pressure)
            pressure_acceleration = current_pressure - previous_pressure

            out["pressure_score"] = current_pressure
            out["pressure_acceleration"] = pressure_acceleration

            # Normalize acceleration magnitude into 0..1 score
            acceleration_score = self._clamp01(abs(pressure_acceleration) * 8.0)
            out["acceleration_score"] = acceleration_score

            if symbol:
                self._prev_pressure_by_symbol[symbol] = current_pressure

            enriched.append(out)

        return enriched