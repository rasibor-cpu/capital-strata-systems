from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _clamp01(v: float) -> float:
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v


def _candle_attr(candle: Any, name: str, default: float = 0.0) -> float:
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

    Preserves:
    - enrich_rows(...)
    - enrich(...)
    - compute_pressure(...)

    Upgrades:
    - nonlinear amplification
    - conviction boost
    - breakout boost
    """

    # ------------------------------------------------
    # ROW PIPELINE INTERFACE (RESTORED)
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
            key=lambda r: float(r.get("pressure_score", 0.0)),
            reverse=True,
        )
        return enriched

    def enrich(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.enrich_rows(rows)

    # ------------------------------------------------
    # CORE PRESSURE LOGIC
    # ------------------------------------------------

    def compute_pressure(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        price = _safe_float(asset.get("price"))
        vwap = _safe_float(asset.get("vwap"))
        candles = asset.get("candles", [])

        volume = _safe_float(asset.get("volume"))
        avg_volume = _safe_float(
            asset.get("avg_volume_24h", asset.get("avg_volume"))
        )

        volatility = _safe_float(asset.get("volatility"))
        compression = _safe_float(asset.get("price_compression"))

        direction = "NEUTRAL"
        if vwap > 0:
            if price > vwap:
                direction = "SHORT"
            elif price < vwap:
                direction = "LONG"

        # -----------------------------
        # VWAP stretch (NONLINEAR)
        # -----------------------------
        stretch = abs(price - vwap) / vwap if vwap > 0 else 0.0
        vwap_pressure = _clamp01((stretch * 12.0) ** 1.3 if stretch > 0 else 0.0)

        # -----------------------------
        # Volume participation (BOOSTED)
        # -----------------------------
        volume_ratio = (volume / avg_volume) if avg_volume > 0 else 0.0
        volume_pressure = _clamp01(volume_ratio ** 1.4 if volume_ratio > 0 else 0.0)

        # -----------------------------
        # Volatility
        # -----------------------------
        volatility_pressure = _clamp01((volatility * 5.0) ** 1.2 if volatility > 0 else 0.0)

        # -----------------------------
        # Compression (pre-breakout)
        # -----------------------------
        compression_pressure = _clamp01(compression ** 1.5 if compression > 0 else 0.0)

        # -----------------------------
        # Candle conviction
        # -----------------------------
        candle_pressure = self._directional_candle_pressure(candles)

        # -----------------------------
        # Range expansion
        # -----------------------------
        range_expansion = self._range_expansion_score(candles)

        # -----------------------------
        # Core blended pressure
        # -----------------------------
        base_pressure = (
            vwap_pressure * 0.25
            + volume_pressure * 0.20
            + volatility_pressure * 0.15
            + compression_pressure * 0.10
            + candle_pressure * 0.15
            + range_expansion * 0.15
        )

        conviction = (candle_pressure + range_expansion) / 2.0
        amplified_pressure = base_pressure * (1.0 + conviction)

        if range_expansion > 0.4:
            amplified_pressure *= 1.25

        pressure_score = _clamp01(amplified_pressure)

        if pressure_score >= 0.65:
            stage = "EXTREME"
        elif pressure_score >= 0.40:
            stage = "BUILDING"
        elif pressure_score >= 0.15:
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

    def _directional_candle_pressure(self, candles: List[Any]) -> float:
        if not candles or len(candles) < 3:
            return 0.0

        recent = candles[-3:]
        scores: List[float] = []

        for c in recent:
            open_ = _candle_attr(c, "open")
            high = _candle_attr(c, "high")
            low = _candle_attr(c, "low")
            close = _candle_attr(c, "close")

            rng = max(high - low, 1e-9)
            body = abs(close - open_)
            ratio = (body / rng) ** 1.3 if body > 0 else 0.0
            scores.append(_clamp01(ratio))

        return sum(scores) / len(scores) if scores else 0.0

    def _range_expansion_score(self, candles: List[Any]) -> float:
        if not candles or len(candles) < 8:
            return 0.0

        recent = candles[-3:]
        prior = candles[-8:-3]

        recent_ranges: List[float] = []
        prior_ranges: List[float] = []

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
            return 0.0

        r = sum(recent_ranges) / len(recent_ranges)
        p = sum(prior_ranges) / len(prior_ranges)

        if p <= 0:
            return 0.0

        expansion = (r - p) / p
        return _clamp01((max(0.0, expansion)) ** 1.3)