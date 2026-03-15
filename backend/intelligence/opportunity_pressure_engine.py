from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


class OpportunityPressureEngine:
    """
    CSS Opportunity Pressure Engine

    Purpose
    -------
    Detect market pressure build-up before outsized moves.

    Current pressure dimensions
    ---------------------------
    1. VWAP stretch
    2. Volume participation
    3. Volatility / range expansion
    4. Compression-release potential
    5. Directional candle-body pressure

    Output
    ------
    Adds:
    - pressure_score
    - pressure_stage
    - pressure_direction
    """

    def __init__(self) -> None:
        self.min_pressure_score = 0.08

    # ------------------------------------------------
    # CSS STANDARD ROW PIPELINE ENTRY
    # ------------------------------------------------
    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            pressure = self.compute_pressure(row)

            new_row = dict(row)
            new_row["pressure_score"] = pressure["pressure"]
            new_row["pressure_stage"] = pressure["stage"]
            new_row["pressure_direction"] = pressure["direction"]

            enriched.append(new_row)

        enriched.sort(
            key=lambda x: float(x.get("pressure_score", 0.0)),
            reverse=True,
        )

        return enriched

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.enrich_rows(rows)

    # ------------------------------------------------
    # CORE PRESSURE CALCULATION
    # ------------------------------------------------
    def compute_pressure(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        price = _safe_float(asset.get("price"), 0.0)
        vwap = _safe_float(asset.get("vwap"), 0.0)

        volume = _safe_float(asset.get("volume"), 0.0)
        avg_volume = _safe_float(asset.get("avg_volume"), 0.0)
        if avg_volume <= 0.0:
            avg_volume = _safe_float(asset.get("avg_volume_24h"), 0.0)

        volatility = _safe_float(asset.get("volatility"), 0.0)
        if volatility <= 0.0:
            volatility = _safe_float(asset.get("avg_volatility"), 0.0)

        compression = _safe_float(asset.get("price_compression"), 0.0)

        candles = asset.get("candles", [])
        candle_pressure = self._directional_candle_pressure(candles)
        range_expansion = self._range_expansion_score(candles)

        direction = "NEUTRAL"
        if vwap > 0 and price > vwap:
            direction = "SHORT"
        elif vwap > 0 and price < vwap:
            direction = "LONG"

        # --------------------------------
        # VWAP stretch
        # --------------------------------
        if vwap > 0:
            vwap_stretch = abs(price - vwap) / vwap
        else:
            vwap_stretch = 0.0

        vwap_pressure = _clamp01(vwap_stretch * 8.0)

        # --------------------------------
        # Volume participation
        # --------------------------------
        if avg_volume > 0:
            volume_ratio = volume / avg_volume
        else:
            volume_ratio = 0.0

        volume_pressure = _clamp01(volume_ratio / 2.0)

        # --------------------------------
        # Volatility contribution
        # --------------------------------
        volatility_pressure = _clamp01(volatility * 4.0 if volatility < 1 else volatility)

        # --------------------------------
        # Compression / release potential
        # --------------------------------
        compression_pressure = _clamp01(compression)

        # --------------------------------
        # Final pressure score
        # --------------------------------
        pressure_score = (
            vwap_pressure * 0.28
            + volume_pressure * 0.18
            + volatility_pressure * 0.14
            + compression_pressure * 0.12
            + candle_pressure * 0.16
            + range_expansion * 0.12
        )

        pressure_score = _clamp01(pressure_score)

        if pressure_score >= 0.55:
            stage = "EXTREME"
        elif pressure_score >= 0.35:
            stage = "BUILDING"
        elif pressure_score >= self.min_pressure_score:
            stage = "EARLY"
        else:
            stage = "NONE"

        return {
            "pressure": round(pressure_score, 4),
            "stage": stage,
            "direction": direction,
        }

    # ------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------
    def _directional_candle_pressure(self, candles: List[Dict[str, Any]]) -> float:
        if not isinstance(candles, list) or len(candles) < 3:
            return 0.0

        recent = candles[-3:]
        body_scores: List[float] = []

        for candle in recent:
            open_ = _safe_float(candle.get("open"), 0.0)
            high = _safe_float(candle.get("high"), 0.0)
            low = _safe_float(candle.get("low"), 0.0)
            close = _safe_float(candle.get("close"), 0.0)

            candle_range = max(high - low, 1e-12)
            candle_body = abs(close - open_)

            body_ratio = candle_body / candle_range
            body_scores.append(_clamp01(body_ratio))

        if not body_scores:
            return 0.0

        return _clamp01(sum(body_scores) / len(body_scores))

    def _range_expansion_score(self, candles: List[Dict[str, Any]]) -> float:
        if not isinstance(candles, list) or len(candles) < 8:
            return 0.0

        recent = candles[-3:]
        prior = candles[-8:-3]

        recent_ranges: List[float] = []
        prior_ranges: List[float] = []

        for candle in recent:
            high = _safe_float(candle.get("high"), 0.0)
            low = _safe_float(candle.get("low"), 0.0)
            close = _safe_float(candle.get("close"), 0.0)
            if close > 0:
                recent_ranges.append(abs(high - low) / close)

        for candle in prior:
            high = _safe_float(candle.get("high"), 0.0)
            low = _safe_float(candle.get("low"), 0.0)
            close = _safe_float(candle.get("close"), 0.0)
            if close > 0:
                prior_ranges.append(abs(high - low) / close)

        if not recent_ranges or not prior_ranges:
            return 0.0

        recent_avg = sum(recent_ranges) / len(recent_ranges)
        prior_avg = sum(prior_ranges) / len(prior_ranges)

        if prior_avg <= 0:
            return 0.0

        expansion = max(0.0, (recent_avg - prior_avg) / prior_avg)
        return _clamp01(expansion)