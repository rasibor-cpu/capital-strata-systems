from __future__ import annotations

from typing import Any, Dict, List


def _safe(v: Any, d: float = 0.0) -> float:
    if v is None:
        return d
    try:
        return float(v)
    except Exception:
        return d


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class OpportunityPressureEngine:
    """
    CSS Opportunity Pressure Engine (v2 – Enhanced, Non-Regression Safe)

    Enhancements:
    - Pressure TYPE detection (BUILDUP / EXPANSION / EXHAUSTION)
    - Momentum vs velocity divergence detection
    - Exhaustion-aware scoring
    - Trade quality classification
    - Stronger direction validation

    Backward compatible outputs:
    - pressure_score
    - pressure_stage
    - pressure_direction

    New outputs:
    - pressure_type
    - pressure_trade_quality
    """

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows or []:
            if not isinstance(row, dict):
                continue

            result = self.compute_pressure(row)

            new_row = dict(row)
            new_row["pressure_score"] = result["pressure"]
            new_row["pressure_stage"] = result["stage"]
            new_row["pressure_direction"] = result["direction"]

            # NEW FIELDS (non-breaking additions)
            new_row["pressure_type"] = result["type"]
            new_row["pressure_trade_quality"] = result["quality"]

            enriched.append(new_row)

        enriched.sort(key=lambda r: _safe(r.get("pressure_score")), reverse=True)
        return enriched

    def compute_pressure(self, asset: Dict[str, Any]) -> Dict[str, Any]:

        price = _safe(asset.get("price"))
        vwap = _safe(asset.get("vwap"))
        momentum = _safe(asset.get("momentum"))
        velocity = _safe(asset.get("velocity"))
        candles = asset.get("candles") or []

        # -----------------------------
        # BASE PRESSURE
        # -----------------------------
        if vwap > 0:
            vwap_dev = abs((price - vwap) / (vwap + 1e-9))
        else:
            vwap_dev = 0.0

        vwap_pressure = _clamp01(vwap_dev * 12.0)
        momentum_pressure = _clamp01(abs(momentum) * 40.0)
        velocity_pressure = _clamp01(abs(velocity) * 55.0)

        base_pressure = (
            vwap_pressure * 0.35
            + momentum_pressure * 0.35
            + velocity_pressure * 0.30
        )

        # -----------------------------
        # CANDLE PRESSURE
        # -----------------------------
        candle_pressure = 0.0
        direction_bias = 0.0
        avg_range_expansion = 0.0

        parsed = []
        for c in candles[-8:]:
            try:
                if isinstance(c, dict):
                    o = _safe(c.get("open"))
                    h = _safe(c.get("high"))
                    l = _safe(c.get("low"))
                    cl = _safe(c.get("close"))
                else:
                    o = _safe(getattr(c, "open", 0.0))
                    h = _safe(getattr(c, "high", 0.0))
                    l = _safe(getattr(c, "low", 0.0))
                    cl = _safe(getattr(c, "close", 0.0))

                if h > 0 and cl > 0:
                    parsed.append((o, h, l, cl))
            except Exception:
                continue

        if len(parsed) >= 3:
            body_scores = []
            close_location_scores = []
            range_scores = []
            signed_bodies = []

            prev_range = None

            for o, h, l, cl in parsed:
                rng = max(h - l, 1e-9)
                body = abs(cl - o)

                body_ratio = body / rng
                close_loc = abs((cl - l) / rng - 0.5) * 2.0
                signed_body = (cl - o) / rng

                range_expansion = 0.0
                if prev_range is not None and prev_range > 0:
                    range_expansion = min(rng / prev_range, 2.0) / 2.0
                prev_range = rng

                body_scores.append(_clamp01(body_ratio))
                close_location_scores.append(_clamp01(close_loc))
                range_scores.append(_clamp01(range_expansion))
                signed_bodies.append(signed_body)

            avg_body = sum(body_scores) / len(body_scores)
            avg_close_loc = sum(close_location_scores) / len(close_location_scores)
            avg_range_expansion = sum(range_scores) / len(range_scores)
            avg_signed_body = sum(signed_bodies) / len(signed_bodies)

            candle_pressure = (
                avg_body * 0.45
                + avg_close_loc * 0.30
                + avg_range_expansion * 0.25
            )

            direction_bias = avg_signed_body

        # -----------------------------
        # FINAL PRESSURE
        # -----------------------------
        pressure = (base_pressure * 0.55) + (candle_pressure * 0.45)
        pressure = _clamp01(pressure)

        # -----------------------------
        # DIVERGENCE DETECTION
        # -----------------------------
        divergence = abs(momentum - velocity)
        divergence_flag = divergence > 0.25

        # -----------------------------
        # PRESSURE TYPE
        # -----------------------------
        pressure_type = "BUILDUP"

        if pressure > 0.65:
            if avg_range_expansion < 0.4 or divergence_flag:
                pressure_type = "EXHAUSTION"
            else:
                pressure_type = "EXPANSION"
        elif pressure > 0.35:
            pressure_type = "BUILDUP"

        # -----------------------------
        # TRADE QUALITY
        # -----------------------------
        trade_quality = "LOW"

        if pressure_type == "EXPANSION" and pressure > 0.55:
            trade_quality = "HIGH"
        elif pressure_type == "BUILDUP" and pressure > 0.35:
            trade_quality = "MEDIUM"
        elif pressure_type == "EXHAUSTION":
            trade_quality = "LOW"

        # -----------------------------
        # DIRECTION (ENHANCED)
        # -----------------------------
        direction = "NEUTRAL"

        if abs(direction_bias) > 0.08:
            direction = "LONG" if direction_bias > 0 else "SHORT"
        elif vwap > 0:
            if price < vwap:
                direction = "LONG"
            elif price > vwap:
                direction = "SHORT"

        # -----------------------------
        # STAGE
        # -----------------------------
        if pressure >= 0.70:
            stage = "EXTREME"
        elif pressure >= 0.45:
            stage = "BUILDING"
        elif pressure >= 0.18:
            stage = "EARLY"
        else:
            stage = "NONE"

        return {
            "pressure": round(pressure, 6),
            "stage": stage,
            "direction": direction,
            "type": pressure_type,
            "quality": trade_quality,
        }