from __future__ import annotations

from typing import Any, Dict, List


class PressureAccelerationEngine:
    """
    CSS Pressure Acceleration Engine
    --------------------------------
    Backward-compatible full replacement.

    Purpose:
    - Computes pressure acceleration safely from row-based market data
    - Preserves prior-cycle memory by symbol
    - Produces a usable first-pass acceleration proxy when no history exists
    - Emits all fields needed by CSS downstream components

    Expected input row keys may include:
    - pressure_score
    - pressure
    - buy_pressure
    - sell_pressure
    - momentum
    - velocity
    - price
    - current_price
    - vwap
    - order_flow_delta
    - trend_strength
    - volatility_score
    - wick_reversal_strength
    - vwap_distance

    Outputs added per row:
    - pressure_acceleration
    - acceleration_score
    - accel
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

    def _clamp(self, value: float, lo: float = -1.0, hi: float = 1.0) -> float:
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value

    def _clamp01(self, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def _derive_pressure(self, row: Dict[str, Any]) -> float:
        explicit_pressure = row.get("pressure_score")
        if explicit_pressure is None:
            explicit_pressure = row.get("pressure")
        if explicit_pressure is not None:
            return self._clamp01(self._safe_float(explicit_pressure, 0.0))

        buy_pressure = self._safe_float(row.get("buy_pressure"), 0.0)
        sell_pressure = self._safe_float(row.get("sell_pressure"), 0.0)
        momentum = self._safe_float(row.get("momentum"), 0.0)
        velocity = self._safe_float(row.get("velocity"), momentum)

        price = self._safe_float(row.get("price"), 0.0)
        current_price = self._safe_float(row.get("current_price"), price)
        vwap = self._safe_float(row.get("vwap"), current_price)

        vwap_dev = 0.0
        if vwap > 0:
            vwap_dev = abs((current_price - vwap) / (vwap + 1e-9))

        pressure_total = abs(buy_pressure) + abs(sell_pressure)
        imbalance = 0.0
        if pressure_total > 1e-9:
            imbalance = abs(buy_pressure - sell_pressure) / pressure_total

        derived = (
            imbalance * 0.40
            + abs(momentum) * 18.0 * 0.25
            + abs(velocity) * 18.0 * 0.20
            + vwap_dev * 25.0 * 0.15
        )

        return self._clamp01(derived)

    def _instantaneous_proxy_acceleration(self, row: Dict[str, Any], current_pressure: float) -> float:
        """
        Used only when no prior pressure exists for a symbol.
        Produces a small bounded non-zero acceleration proxy from
        current market-state dynamics so first-cycle rows are not dead-zero.
        """
        buy_pressure = self._safe_float(row.get("buy_pressure"), 0.0)
        sell_pressure = self._safe_float(row.get("sell_pressure"), 0.0)
        momentum = self._safe_float(row.get("momentum"), 0.0)
        velocity = self._safe_float(row.get("velocity"), momentum)
        order_flow_delta = self._safe_float(row.get("order_flow_delta"), 0.0)
        trend_strength = self._safe_float(row.get("trend_strength"), 0.0)
        volatility_score = self._safe_float(row.get("volatility_score"), 0.0)
        wick_reversal_strength = self._safe_float(row.get("wick_reversal_strength"), 0.0)
        vwap_distance = self._safe_float(row.get("vwap_distance"), 0.0)

        pressure_total = abs(buy_pressure) + abs(sell_pressure)
        imbalance = 0.0
        if pressure_total > 1e-9:
            imbalance = (buy_pressure - sell_pressure) / pressure_total

        flow_component = self._clamp(order_flow_delta / 100.0)
        mv_component = self._clamp((momentum * 6.0) + (velocity * 4.0))
        trend_component = self._clamp(trend_strength)
        reversal_dampener = self._clamp(
            abs(wick_reversal_strength) * 0.5 + abs(vwap_distance) * 0.25,
            0.0,
            1.0,
        )

        raw = (
            current_pressure * 0.25
            + imbalance * 0.25
            + flow_component * 0.20
            + mv_component * 0.20
            + trend_component * 0.10
        )

        raw = raw * (1.0 - 0.35 * reversal_dampener)
        return self._clamp(raw)

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows or []:
            if not isinstance(row, dict):
                continue

            out = dict(row)

            symbol = str(out.get("symbol") or out.get("asset") or "")
            current_pressure = self._derive_pressure(out)

            if symbol and symbol in self._prev_pressure_by_symbol:
                previous_pressure = self._prev_pressure_by_symbol[symbol]
                pressure_acceleration = current_pressure - previous_pressure
            else:
                pressure_acceleration = self._instantaneous_proxy_acceleration(out, current_pressure)

            pressure_acceleration = self._clamp(pressure_acceleration)

            out["pressure_score"] = current_pressure
            out["pressure_acceleration"] = pressure_acceleration
            out["acceleration_score"] = self._clamp01(abs(pressure_acceleration))
            out["accel"] = pressure_acceleration

            if symbol:
                self._prev_pressure_by_symbol[symbol] = current_pressure

            enriched.append(out)

        return enriched