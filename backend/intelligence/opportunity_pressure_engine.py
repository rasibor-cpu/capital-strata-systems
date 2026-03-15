from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _clamp01(v: float) -> float:
    if v < 0:
        return 0
    if v > 1:
        return 1
    return v


def _candle_attr(candle: Any, name: str, default: float = 0.0) -> float:
    """
    Safe candle accessor supporting:

    - Candle objects
    - dict candles
    - tuple/list candles
    """

    if hasattr(candle, name):
        return _safe_float(getattr(candle, name), default)

    if isinstance(candle, dict):
        return _safe_float(candle.get(name, default), default)

    if isinstance(candle, (list, tuple)):

        idx_map = {
            "ts": 0,
            "open": 1,
            "high": 2,
            "low": 3,
            "close": 4,
            "volume": 5,
        }

        idx = idx_map.get(name)

        if idx is not None and len(candle) > idx:
            return _safe_float(candle[idx], default)

    return default


class OpportunityPressureEngine:
    """
    CSS Opportunity Pressure Engine

    Calculates market pressure leading to potential price expansion.
    """

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        enriched = []

        for row in rows:

            pressure = self.compute_pressure(row)

            new_row = dict(row)

            new_row["pressure_score"] = pressure["pressure"]
            new_row["pressure_stage"] = pressure["stage"]
            new_row["pressure_direction"] = pressure["direction"]

            enriched.append(new_row)

        enriched.sort(
            key=lambda r: float(r.get("pressure_score", 0)),
            reverse=True,
        )

        return enriched

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.enrich_rows(rows)

    # ------------------------------------------------

    def compute_pressure(self, asset: Dict[str, Any]) -> Dict[str, Any]:

        price = _safe_float(asset.get("price"))
        vwap = _safe_float(asset.get("vwap"))

        candles = asset.get("candles", [])

        volume = _safe_float(asset.get("volume"))
        avg_volume = _safe_float(asset.get("avg_volume_24h"))

        volatility = _safe_float(asset.get("volatility"))
        compression = _safe_float(asset.get("price_compression"))

        # --------------------------------

        direction = "NEUTRAL"

        if vwap > 0:

            if price > vwap:
                direction = "SHORT"

            elif price < vwap:
                direction = "LONG"

        # --------------------------------
        # VWAP stretch
        # --------------------------------

        if vwap > 0:
            stretch = abs(price - vwap) / vwap
        else:
            stretch = 0

        vwap_pressure = _clamp01(stretch * 8)

        # --------------------------------
        # volume participation
        # --------------------------------

        if avg_volume > 0:
            volume_ratio = volume / avg_volume
        else:
            volume_ratio = 0

        volume_pressure = _clamp01(volume_ratio / 2)

        # --------------------------------
        # volatility
        # --------------------------------

        volatility_pressure = _clamp01(volatility * 4)

        # --------------------------------
        # compression
        # --------------------------------

        compression_pressure = _clamp01(compression)

        # --------------------------------
        # candle pressure
        # --------------------------------

        candle_pressure = self._directional_candle_pressure(candles)

        # --------------------------------
        # range expansion
        # --------------------------------

        range_expansion = self._range_expansion_score(candles)

        # --------------------------------
        # final score
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
        elif pressure_score >= 0.08:
            stage = "EARLY"
        else:
            stage = "NONE"

        return {
            "pressure": round(pressure_score, 4),
            "stage": stage,
            "direction": direction,
        }

    # ------------------------------------------------

    def _directional_candle_pressure(self, candles: List[Any]) -> float:

        if not candles or len(candles) < 3:
            return 0

        recent = candles[-3:]

        scores = []

        for c in recent:

            open_ = _candle_attr(c, "open")
            high = _candle_attr(c, "high")
            low = _candle_attr(c, "low")
            close = _candle_attr(c, "close")

            rng = max(high - low, 1e-9)
            body = abs(close - open_)

            ratio = body / rng

            scores.append(_clamp01(ratio))

        if not scores:
            return 0

        return sum(scores) / len(scores)

    # ------------------------------------------------

    def _range_expansion_score(self, candles: List[Any]) -> float:

        if not candles or len(candles) < 8:
            return 0

        recent = candles[-3:]
        prior = candles[-8:-3]

        recent_ranges = []
        prior_ranges = []

        for c in recent:

            high = _candle_attr(c, "high")
            low = _candle_attr(c, "low")
            close = _candle_attr(c, "close")

            if close > 0:
                recent_ranges.append(abs(high - low) / close)

        for c in prior:

            high = _candle_attr(c, "high")
            low = _candle_attr(c, "low")
            close = _candle_attr(c, "close")

            if close > 0:
                prior_ranges.append(abs(high - low) / close)

        if not recent_ranges or not prior_ranges:
            return 0

        r = sum(recent_ranges) / len(recent_ranges)
        p = sum(prior_ranges) / len(prior_ranges)

        if p <= 0:
            return 0

        expansion = (r - p) / p

        return _clamp01(max(0, expansion))