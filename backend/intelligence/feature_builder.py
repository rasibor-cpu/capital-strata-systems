from __future__ import annotations

from typing import Any, Dict, List, Optional


class FeatureBuilder:
    """
    CSS Feature Builder

    Purpose
    -------
    Build stable, normalized market features from runtime asset payloads.

    Design goals
    ------------
    - Backward-compatible enrich_rows(rows) interface
    - Accept both:
        1) row["candles"] as a raw list of candles
        2) row["candles"] as a dict payload containing {"candles": [...], ...}
    - Safely handle mixed candle formats:
        - dict candles with keys like open/high/low/close/volume
        - list/tuple candles in common exchange orderings
    - Never crash the dashboard because of malformed market data
    """

    def enrich_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for row in rows:
            try:
                out = dict(row)

                candles = self._normalize_candles(out.get("candles", []))
                out["candles"] = candles
                out["candles_count"] = len(candles)

                if not candles:
                    out.setdefault("price", 0.0)
                    out.setdefault("open", 0.0)
                    out.setdefault("high", 0.0)
                    out.setdefault("low", 0.0)
                    out.setdefault("close", 0.0)
                    out.setdefault("volume", 0.0)
                    out.setdefault("avg_volume", 0.0)
                    out.setdefault("volume_ratio", 0.0)
                    out.setdefault("price_change_pct", 0.0)
                    out.setdefault("momentum", 0.0)
                    out.setdefault("volatility", 0.0)
                    out.setdefault("returns_std", 0.0)
                    out.setdefault("range_pct", 0.0)
                    out.setdefault("sma_fast", 0.0)
                    out.setdefault("sma_slow", 0.0)
                    out.setdefault("trend_strength", 0.0)
                    enriched.append(out)
                    continue

                last = candles[-1]
                first = candles[0]

                last_open = self._candle_open(last)
                last_high = self._candle_high(last)
                last_low = self._candle_low(last)
                last_close = self._candle_close(last)
                last_volume = self._candle_volume(last)

                first_close = self._candle_close(first)

                avg_volume = self._compute_avg_volume(candles, window=20)
                sma_fast = self._compute_sma(candles, window=10)
                sma_slow = self._compute_sma(candles, window=30)
                momentum = self._compute_momentum(candles, window=10)
                volatility = self._compute_volatility(candles, window=20)
                returns_std = volatility
                range_pct = self._compute_range_pct(last_high, last_low, last_close)
                price_change_pct = self._pct_change(first_close, last_close)
                volume_ratio = (last_volume / avg_volume) if avg_volume > 0 else 0.0

                if sma_slow > 0:
                    trend_strength = (sma_fast - sma_slow) / sma_slow
                else:
                    trend_strength = 0.0

                out["open"] = last_open
                out["high"] = last_high
                out["low"] = last_low
                out["close"] = last_close
                out["price"] = last_close
                out["volume"] = last_volume

                out["avg_volume"] = avg_volume
                out["volume_ratio"] = volume_ratio
                out["price_change_pct"] = price_change_pct
                out["momentum"] = momentum
                out["volatility"] = volatility
                out["returns_std"] = returns_std
                out["range_pct"] = range_pct
                out["sma_fast"] = sma_fast
                out["sma_slow"] = sma_slow
                out["trend_strength"] = trend_strength

                enriched.append(out)

            except Exception:
                # Fail-soft design: preserve row and fill neutral defaults
                fallback = dict(row)
                fallback["candles"] = self._normalize_candles(fallback.get("candles", []))
                fallback.setdefault("candles_count", len(fallback["candles"]))
                fallback.setdefault("price", 0.0)
                fallback.setdefault("open", 0.0)
                fallback.setdefault("high", 0.0)
                fallback.setdefault("low", 0.0)
                fallback.setdefault("close", 0.0)
                fallback.setdefault("volume", 0.0)
                fallback.setdefault("avg_volume", 0.0)
                fallback.setdefault("volume_ratio", 0.0)
                fallback.setdefault("price_change_pct", 0.0)
                fallback.setdefault("momentum", 0.0)
                fallback.setdefault("volatility", 0.0)
                fallback.setdefault("returns_std", 0.0)
                fallback.setdefault("range_pct", 0.0)
                fallback.setdefault("sma_fast", 0.0)
                fallback.setdefault("sma_slow", 0.0)
                fallback.setdefault("trend_strength", 0.0)
                enriched.append(fallback)

        return enriched

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_candles(self, candles: Any) -> List[Any]:
        """
        Accept either:
        - list of candles
        - dict payload containing a 'candles' key
        - anything else -> []
        """
        if isinstance(candles, dict):
            inner = candles.get("candles", [])
            if isinstance(inner, list):
                return inner
            return []

        if isinstance(candles, list):
            return candles

        return []

    # ============================================================
    # SAFE NUMERIC HELPERS
    # ============================================================

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _pct_change(self, old: float, new: float) -> float:
        if old == 0:
            return 0.0
        return (new - old) / old

    # ============================================================
    # CANDLE FIELD EXTRACTION
    # Supports dict candles and list/tuple candles
    # Common list shape assumptions:
    #   [timestamp, low, high, open, close, volume]
    # Fallbacks are defensive and non-fatal.
    # ============================================================

    def _candle_open(self, candle: Any) -> float:
        if isinstance(candle, dict):
            for key in ("open", "o"):
                if key in candle:
                    return self._safe_float(candle.get(key))
            return 0.0

        if isinstance(candle, (list, tuple)):
            if len(candle) >= 4:
                return self._safe_float(candle[3])
        return 0.0

    def _candle_high(self, candle: Any) -> float:
        if isinstance(candle, dict):
            for key in ("high", "h"):
                if key in candle:
                    return self._safe_float(candle.get(key))
            return 0.0

        if isinstance(candle, (list, tuple)):
            if len(candle) >= 3:
                return self._safe_float(candle[2])
        return 0.0

    def _candle_low(self, candle: Any) -> float:
        if isinstance(candle, dict):
            for key in ("low", "l"):
                if key in candle:
                    return self._safe_float(candle.get(key))
            return 0.0

        if isinstance(candle, (list, tuple)):
            if len(candle) >= 2:
                return self._safe_float(candle[1])
        return 0.0

    def _candle_close(self, candle: Any) -> float:
        if isinstance(candle, dict):
            for key in ("close", "c", "price"):
                if key in candle:
                    return self._safe_float(candle.get(key))
            return 0.0

        if isinstance(candle, (list, tuple)):
            if len(candle) >= 5:
                return self._safe_float(candle[4])
        return 0.0

    def _candle_volume(self, candle: Any) -> float:
        if isinstance(candle, dict):
            for key in ("volume", "v"):
                if key in candle:
                    return self._safe_float(candle.get(key))
            return 0.0

        if isinstance(candle, (list, tuple)):
            if len(candle) >= 6:
                return self._safe_float(candle[5])
        return 0.0

    # ============================================================
    # FEATURE COMPUTATIONS
    # ============================================================

    def _compute_avg_volume(self, candles: Any, window: int = 20) -> float:
        candles = self._normalize_candles(candles)

        if not candles:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles

        volumes: List[float] = []
        for c in subset:
            volumes.append(self._candle_volume(c))

        if not volumes:
            return 0.0

        return sum(volumes) / len(volumes)

    def _compute_sma(self, candles: Any, window: int = 10) -> float:
        candles = self._normalize_candles(candles)

        if not candles:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles
        closes = [self._candle_close(c) for c in subset]
        closes = [c for c in closes if c > 0]

        if not closes:
            return 0.0

        return sum(closes) / len(closes)

    def _compute_momentum(self, candles: Any, window: int = 10) -> float:
        candles = self._normalize_candles(candles)

        if len(candles) < 2:
            return 0.0

        if len(candles) > window:
            start_candle = candles[-window]
        else:
            start_candle = candles[0]

        end_candle = candles[-1]

        start_close = self._candle_close(start_candle)
        end_close = self._candle_close(end_candle)

        return self._pct_change(start_close, end_close)

    def _compute_volatility(self, candles: Any, window: int = 20) -> float:
        candles = self._normalize_candles(candles)

        if len(candles) < 3:
            return 0.0

        subset = candles[-window:] if len(candles) >= window else candles
        closes = [self._candle_close(c) for c in subset]
        closes = [c for c in closes if c > 0]

        if len(closes) < 2:
            return 0.0

        returns: List[float] = []
        for i in range(1, len(closes)):
            prev_close = closes[i - 1]
            curr_close = closes[i]
            if prev_close > 0:
                returns.append((curr_close - prev_close) / prev_close)

        if not returns:
            return 0.0

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        return variance ** 0.5

    def _compute_range_pct(self, high: float, low: float, close: float) -> float:
        if close <= 0:
            return 0.0
        return max(0.0, (high - low) / close)