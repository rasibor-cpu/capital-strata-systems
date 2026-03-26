from __future__ import annotations

from typing import Any, Dict, List


def _safe(v, d=0.0):
    try:
        return float(v)
    except:
        return d


def _clamp01(v: float) -> float:
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v


class OpportunityPressureEngine:
    """
    HYBRID PRESSURE ENGINE

    Uses:
    1. Candle logic (if available)
    2. Fallback logic (price/VWAP/momentum)

    Ensures pressure NEVER stays zero again.
    """

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched = []

        for row in rows:
            result = self.compute_pressure(row)

            new_row = dict(row)
            new_row["pressure_score"] = result["pressure"]
            new_row["pressure_stage"] = result["stage"]
            new_row["pressure_direction"] = result["direction"]

            enriched.append(new_row)

        enriched.sort(key=lambda r: r.get("pressure_score", 0), reverse=True)
        return enriched

    def compute_pressure(self, asset: Dict[str, Any]) -> Dict[str, Any]:

        price = _safe(asset.get("price"))
        vwap = _safe(asset.get("vwap"))
        momentum = _safe(asset.get("momentum"))
        velocity = _safe(asset.get("velocity"))
        candles = asset.get("candles", [])

        # -----------------------------
        # BASE (always available)
        # -----------------------------
        if vwap > 0:
            vwap_dev = (price - vwap) / vwap
        else:
            vwap_dev = 0.0

        vwap_pressure = _clamp01(abs(vwap_dev) * 5.0)
        momentum_pressure = _clamp01(abs(momentum) * 10.0)
        velocity_boost = _clamp01(abs(velocity) * 15.0)

        base_pressure = (
            vwap_pressure * 0.5 +
            momentum_pressure * 0.3 +
            velocity_boost * 0.2
        )

        # -----------------------------
        # ADVANCED (only if candles exist)
        # -----------------------------
        candle_pressure = 0.0
        expansion = 0.0

        if candles and len(candles) >= 3:
            candle_pressure = 0.3
            if len(candles) >= 8:
                expansion = 0.2

        # -----------------------------
        # FINAL PRESSURE
        # -----------------------------
        pressure = base_pressure + candle_pressure + expansion
        pressure = _clamp01(pressure)

        # -----------------------------
        # DIRECTION
        # -----------------------------
        direction = "NEUTRAL"
        if vwap > 0:
            if price > vwap:
                direction = "SHORT"
            elif price < vwap:
                direction = "LONG"

        # -----------------------------
        # STAGE
        # -----------------------------
        if pressure > 0.65:
            stage = "EXTREME"
        elif pressure > 0.35:
            stage = "BUILDING"
        elif pressure > 0.10:
            stage = "EARLY"
        else:
            stage = "NONE"

        return {
            "pressure": round(pressure, 4),
            "stage": stage,
            "direction": direction,
        }