from __future__ import annotations

from typing import Any, Dict, List


class FeatureBuilder:
    """
    CSS Feature Builder

    Enriches runtime asset rows with the core derived features required by:
    - regime engine
    - opportunity pressure engine
    - pressure acceleration engine
    - AI opportunity scorer
    - optimizer
    """

    def __init__(self) -> None:
        pass

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _get_close(self, candle: Dict[str, Any]) -> float:
        return self._safe_float(candle.get("close"))

    def _get_high(self, candle: Dict[str, Any]) -> float:
        return self._safe_float(candle.get("high"))

    def _get_low(self, candle: Dict[str, Any]) -> float:
        return self._safe_float(candle.get("low"))

    def _get_volume(self, candle: Dict[str, Any]) -> float:
        return self._safe_float(candle.get("volume"))

    def _compute_avg_volume(self, candles: List[Dict[str, Any]], window: int = 20) -> float:
        if not candles:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles
        vols = [self._get_volume(c) for c in subset if self._get_volume(c) > 0]

        if not vols:
            return 0.0

        return sum(vols) / len(vols)

    def _compute_volatility(self, candles: List[Dict[str, Any]], window: int = 20) -> float:
        if not candles:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles
        rel_ranges: List[float] = []

        for c in subset:
            high = self._get_high(c)
            low = self._get_low(c)
            close = self._get_close(c)

            if close > 0 and high >= low:
                rel_ranges.append((high - low) / close)

        if not rel_ranges:
            return 0.0

        return sum(rel_ranges) / len(rel_ranges)

    def _compute_price_compression(self, candles: List[Dict[str, Any]], window: int = 20) -> float:
        """
        Higher value = tighter recent compression.
        Output scaled into [0, 1].
        """
        if len(candles) < 5:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles
        closes = [self._get_close(c) for c in subset if self._get_close(c) > 0]
        highs = [self._get_high(c) for c in subset]
        lows = [self._get_low(c) for c in subset]

        if not closes or not highs or not lows:
            return 0.0

        price_ref = closes[-1]
        if price_ref <= 0:
            return 0.0

        total_range = max(highs) - min(lows)
        norm_range = total_range / price_ref

        if norm_range <= 0:
            return 1.0

        # tighter range => larger compression score
        compression = 1.0 - min(norm_range / 0.08, 1.0)
        return max(0.0, min(compression, 1.0))

    def _compute_momentum_window(self, candles: List[Dict[str, Any]], window: int = 12) -> float:
        if len(candles) < 2:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles
        if len(subset) < 2:
            return 0.0

        first_close = self._get_close(subset[0])
        last_close = self._get_close(subset[-1])

        if first_close <= 0:
            return 0.0

        return (last_close - first_close) / first_close

    def _compute_vwap_distance(self, price: float, vwap: float) -> float:
        if price <= 0 or vwap <= 0:
            return 0.0
        return (price - vwap) / vwap

    def enrich_rows(self, rows: List[Dict[str, Any]], config: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        config = config or {}

        for row in rows:
            candles = row.get("candles", [])
            price = self._safe_float(row.get("price"))
            vwap = self._safe_float(row.get("vwap"))

            avg_volume = self._compute_avg_volume(candles, window=20)
            volatility = self._compute_volatility(candles, window=20)
            price_compression = self._compute_price_compression(candles, window=20)
            momentum_window = self._compute_momentum_window(candles, window=12)
            vwap_distance = self._compute_vwap_distance(price, vwap)

            current_volume = 0.0
            if candles:
                current_volume = self._get_volume(candles[-1])

            # Preserve existing fields, enrich missing ones
            row["avg_volume"] = avg_volume
            row["avg_volume_20"] = avg_volume
            row["volume"] = current_volume
            row["volatility"] = volatility
            row["volatility_20"] = volatility
            row["price_compression"] = price_compression
            row["momentum_window"] = momentum_window
            row["vwap_distance"] = vwap_distance

            # Optional convenience aliases for downstream compatibility
            row["compression"] = price_compression
            row["momentum"] = row.get("momentum", momentum_window)

        return rows