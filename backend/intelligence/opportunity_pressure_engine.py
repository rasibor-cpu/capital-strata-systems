from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class OpportunityPressureEngine:
    """
    CSS Opportunity Pressure Engine

    Detects reversal / exhaustion pressure building in an asset.
    This enriches rows before AI scoring.
    """

    def __init__(self) -> None:
        self.vwap_distance_weight = 0.30
        self.range_extension_weight = 0.20
        self.exhaustion_weight = 0.20
        self.reversal_weight = 0.20
        self.momentum_weight = 0.10

    def _distance_from_vwap(self, price: float, vwap: float) -> float:
        if vwap <= 0:
            return 0.0
        distance = abs(price - vwap) / vwap
        return min(1.0, distance * 10.0)

    def _range_extension(self, price: float, high: float, low: float) -> float:
        if high <= low:
            return 0.0

        mid = (high + low) / 2.0
        half_range = (high - low) / 2.0

        if half_range <= 0:
            return 0.0

        extension = abs(price - mid) / half_range
        return min(1.0, extension)

    def _exhaustion(self, trend_efficiency: float) -> float:
        return 1.0 - min(1.0, max(0.0, trend_efficiency))

    def _reversal_bias(self, wick_strength: float, rejection_strength: float) -> float:
        value = (wick_strength + rejection_strength) / 2.0
        return min(1.0, max(0.0, value))

    def _momentum_pressure(self, momentum: float) -> float:
        return min(1.0, abs(momentum) * 10.0)

    def compute_pressure(self, row: Dict[str, Any]) -> Dict[str, Any]:
        price = _safe_float(row.get("price"))
        vwap = _safe_float(row.get("vwap"))

        high = _safe_float(row.get("recent_high"))
        low = _safe_float(row.get("recent_low"))

        wick = _safe_float(row.get("wick_reversal_strength"))
        rejection = _safe_float(row.get("rejection_strength"))

        momentum = _safe_float(row.get("momentum"))
        trend_eff = _safe_float(row.get("trend_efficiency"))

        pressure_distance = self._distance_from_vwap(price, vwap)
        pressure_range = self._range_extension(price, high, low)
        pressure_exhaustion = self._exhaustion(trend_eff)
        pressure_reversal = self._reversal_bias(wick, rejection)
        pressure_momentum = self._momentum_pressure(momentum)

        pressure_score = (
            pressure_distance * self.vwap_distance_weight
            + pressure_range * self.range_extension_weight
            + pressure_exhaustion * self.exhaustion_weight
            + pressure_reversal * self.reversal_weight
            + pressure_momentum * self.momentum_weight
        )

        pressure_score = max(0.0, min(1.0, pressure_score))

        if pressure_score >= 0.70:
            pressure_label = "HIGH"
        elif pressure_score >= 0.50:
            pressure_label = "MEDIUM"
        else:
            pressure_label = "LOW"

        return {
            "pressure_score": round(pressure_score, 4),
            "pressure_label": pressure_label,
            "pressure_distance": round(pressure_distance, 4),
            "pressure_range": round(pressure_range, 4),
            "pressure_exhaustion": round(pressure_exhaustion, 4),
            "pressure_reversal": round(pressure_reversal, 4),
            "pressure_momentum": round(pressure_momentum, 4),
        }

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            pressure = self.compute_pressure(row)
            new_row = dict(row)
            new_row.update(pressure)
            enriched.append(new_row)

        return enriched