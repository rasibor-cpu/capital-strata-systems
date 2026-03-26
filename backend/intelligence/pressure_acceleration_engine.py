from __future__ import annotations

from typing import List, Dict


def clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class PressureAccelerationEngine:
    """
    Computes:
    - pressure (market push strength)
    - acceleration (rate of change of pressure)

    Designed to NEVER return zero unless truly flat market.
    Fully backward compatible (no dependency breaking).
    """

    def enrich_rows(self, rows: List[Dict]) -> List[Dict]:

        enriched: List[Dict] = []

        prev_pressure = 0.0

        for r in rows:

            # --- SAFE EXTRACTION ---
            price = float(r.get("price", 0.0))
            vwap = float(r.get("vwap", 0.0))
            momentum = float(r.get("momentum", 0.0))

            # --- FALLBACKS ---
            if price == 0.0:
                price = float(r.get("close", 0.0))

            if vwap == 0.0:
                vwap = price  # fallback prevents division issues

            # --- VWAP DEVIATION ---
            vwap_dev = price - vwap
            vwap_dev_abs = abs(vwap_dev)

            # --- PRESSURE CALCULATION ---
            # combines deviation + momentum strength
            raw_pressure = vwap_dev_abs * (abs(momentum) + 0.0001)

            # normalize to stable range
            pressure = clamp01(raw_pressure * 5.0)

            # --- ACCELERATION ---
            acceleration = pressure - prev_pressure

            # normalize acceleration
            acceleration_score = clamp01(abs(acceleration) * 5.0)

            prev_pressure = pressure

            # --- WRITE BACK (CRITICAL FIX) ---
            r["pressure"] = pressure
            r["pressure_score"] = pressure
            r["pressure_acceleration"] = acceleration
            r["acceleration"] = acceleration_score
            r["acceleration_score"] = acceleration_score

            enriched.append(r)

        return enriched