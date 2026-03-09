from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

import requests

COINBASE_API = "https://api.exchange.coinbase.com"


class PreBreakoutScanner:
    """
    CSS Pre-Breakout Scanner

    Goal:
    Find coins that are setting up for a potential sharp move before the breakout
    is obvious.

    Core idea:
    - Compression: recent ranges tighten
    - Pressure: price lifts toward upper range / VWAP
    - Relative volume: latest volume expands vs recent average
    - Momentum improvement: short-term slope improves
    - Liquidity: avoid dead markets
    """

    def __init__(self, max_assets: int = 200, granularity: int = 900, candles_needed: int = 30) -> None:
        self.max_assets = max_assets
        self.granularity = granularity
        self.candles_needed = candles_needed
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Capital-Strata-Systems/1.0",
                "Accept": "application/json",
            }
        )

    def _get_products(self) -> List[str]:
        url = f"{COINBASE_API}/products"
        r = self.session.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        symbols: List[str] = []
        for p in data:
            if p.get("quote_currency") != "USD":
                continue
            if p.get("status") != "online":
                continue

            pid = p.get("id")
            if not isinstance(pid, str):
                continue
            if not pid.endswith("-USD"):
                continue
            if pid.startswith("USD-"):
                continue

            symbols.append(pid)

        symbols.sort()
        return symbols[: self.max_assets]

    def _get_candles(self, product: str) -> Optional[List[Dict[str, float]]]:
        url = f"{COINBASE_API}/products/{product}/candles"
        r = self.session.get(
            url,
            params={"granularity": self.granularity},
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()

        candles: List[Dict[str, float]] = []
        for row in raw:
            if not isinstance(row, list) or len(row) < 6:
                continue

            ts, low, high, open_, close, volume = row[:6]
            candles.append(
                {
                    "ts": float(ts),
                    "low": float(low),
                    "high": float(high),
                    "open": float(open_),
                    "close": float(close),
                    "volume": float(volume),
                }
            )

        candles.sort(key=lambda x: x["ts"])

        if len(candles) < self.candles_needed:
            return None

        return candles[-self.candles_needed :]

    @staticmethod
    def _compute_vwap(candles: List[Dict[str, float]], window: int = 20) -> float:
        window_candles = candles[-window:]
        pv_sum = 0.0
        vol_sum = 0.0

        for c in window_candles:
            typical = (c["high"] + c["low"] + c["close"]) / 3.0
            vol = c["volume"]
            pv_sum += typical * vol
            vol_sum += vol

        if vol_sum <= 0:
            return candles[-1]["close"]

        return pv_sum / vol_sum

    @staticmethod
    def _range_pct(candle: Dict[str, float]) -> float:
        close = candle["close"]
        if close <= 0:
            return 0.0
        return ((candle["high"] - candle["low"]) / close) * 100.0

    def _score_asset(self, product: str) -> Optional[Dict[str, Any]]:
        candles = self._get_candles(product)
        if not candles:
            return None

        closes = [c["close"] for c in candles]
        volumes = [c["volume"] for c in candles]
        latest = candles[-1]

        latest_close = latest["close"]
        if latest_close <= 0:
            return None

        # ---- Liquidity proxy ----
        quote_volume = 0.0
        for c in candles[-20:]:
            typical = (c["high"] + c["low"] + c["close"]) / 3.0
            quote_volume += typical * c["volume"]

        if quote_volume < 25000:
            return None

        # ---- Compression / contraction ----
        older_ranges = [self._range_pct(c) for c in candles[-20:-5]]
        recent_ranges = [self._range_pct(c) for c in candles[-5:]]

        if not older_ranges or not recent_ranges:
            return None

        older_avg_range = sum(older_ranges) / len(older_ranges)
        recent_avg_range = sum(recent_ranges) / len(recent_ranges)

        compression_ratio = 0.0
        if older_avg_range > 0:
            compression_ratio = recent_avg_range / older_avg_range

        # Lower compression ratio is better for pre-breakout setup.
        compression_score = max(0.0, 1.0 - min(compression_ratio, 1.5) / 1.5)

        # ---- Volume expansion ----
        avg_recent_volume = sum(volumes[-10:-1]) / max(len(volumes[-10:-1]), 1)
        latest_volume = volumes[-1]
        volume_spike = 0.0
        if avg_recent_volume > 0:
            volume_spike = latest_volume / avg_recent_volume

        volume_score = min(volume_spike / 2.5, 1.0)

        # ---- VWAP pressure / reclaim ----
        vwap = self._compute_vwap(candles, 20)
        vwap_distance_pct = ((latest_close / vwap) - 1.0) * 100.0

        # Pre-breakout often happens near or slightly above VWAP, not deeply below.
        if vwap_distance_pct < -3.0:
            vwap_score = 0.0
        elif vwap_distance_pct < 0.0:
            vwap_score = 0.35
        elif vwap_distance_pct <= 2.0:
            vwap_score = 1.0
        else:
            vwap_score = 0.65

        # ---- Momentum improvement ----
        short_momentum = 0.0
        if closes[-5] > 0:
            short_momentum = ((closes[-1] / closes[-5]) - 1.0) * 100.0

        medium_momentum = 0.0
        if closes[-15] > 0:
            medium_momentum = ((closes[-1] / closes[-15]) - 1.0) * 100.0

        # Prefer assets turning positive but not already too extended.
        if short_momentum < -2.0:
            momentum_score = 0.0
        elif short_momentum <= 4.0:
            momentum_score = 0.70
        elif short_momentum <= 10.0:
            momentum_score = 1.0
        else:
            momentum_score = 0.45

        # ---- Position inside local range ----
        local_low = min(c["low"] for c in candles[-10:])
        local_high = max(c["high"] for c in candles[-10:])
        if local_high > local_low:
            range_position = (latest_close - local_low) / (local_high - local_low)
        else:
            range_position = 0.5

        # Near upper half of range is constructive for pre-breakout.
        if range_position < 0.40:
            range_position_score = 0.0
        elif range_position < 0.65:
            range_position_score = 0.55
        else:
            range_position_score = 1.0

        # ---- Stability / smoothness ----
        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] <= 0:
                continue
            returns.append(((closes[i] / closes[i - 1]) - 1.0) * 100.0)

        realized_vol = statistics.stdev(returns) if len(returns) >= 2 else 0.0

        # Too chaotic is less attractive for pre-breakout staging.
        if realized_vol <= 1.0:
            stability_score = 1.0
        elif realized_vol <= 3.0:
            stability_score = 0.8
        elif realized_vol <= 6.0:
            stability_score = 0.55
        else:
            stability_score = 0.25

        # ---- Final weighted score ----
        score = (
            compression_score * 22.0
            + volume_score * 20.0
            + vwap_score * 18.0
            + momentum_score * 15.0
            + range_position_score * 15.0
            + stability_score * 10.0
        )

        regime = "PRE_BREAKOUT"
        if medium_momentum < 0:
            regime = "BASE_BUILDING"

        confidence_band = "LOW"
        if score >= 80:
            confidence_band = "HIGH"
        elif score >= 65:
            confidence_band = "GOOD"
        elif score >= 50:
            confidence_band = "MODERATE"

        priority = "IGNORE"
        if score >= 80:
            priority = "TRADE_NOW"
        elif score >= 65:
            priority = "WATCH_CLOSELY"
        elif score >= 50:
            priority = "WATCHLIST"

        explanation = (
            f"{product} compression={compression_ratio:.2f}, "
            f"vol_spike={volume_spike:.2f}, "
            f"vwap_dist={vwap_distance_pct:.2f}%, "
            f"short_mom={short_momentum:.2f}%, "
            f"range_pos={range_position:.2f}"
        )

        return {
            "symbol": product,
            "asset_class": "CRYPTO",
            "signal": "BUY",
            "regime": regime,
            "opportunity_score": round(score, 2),
            "confidence_band": confidence_band,
            "action_priority": priority,
            "explanation": explanation,
            "quote_volume_usd": round(quote_volume, 2),
            "vwap_distance_pct": round(vwap_distance_pct, 4),
            "short_momentum_pct": round(short_momentum, 4),
            "medium_momentum_pct": round(medium_momentum, 4),
            "compression_ratio": round(compression_ratio, 4),
            "volume_spike": round(volume_spike, 4),
            "range_position": round(range_position, 4),
        }

    def run(self) -> List[Dict[str, Any]]:
        products = self._get_products()
        results: List[Dict[str, Any]] = []

        for product in products:
            try:
                scored = self._score_asset(product)
                if scored:
                    results.append(scored)
            except Exception:
                continue

        results.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return results[:20]


def print_pre_breakout_results(results: List[Dict[str, Any]]) -> None:
    print("\n=== CSS PRE-BREAKOUT SCANNER ===\n")
    for item in results[:10]:
        print(
            f"{item['symbol']:<12} "
            f"score={item['opportunity_score']:>7.2f} "
            f"band={item['confidence_band']:<8} "
            f"regime={item['regime']:<14} "
            f"vol_spike={item['volume_spike']:.2f} "
            f"compression={item['compression_ratio']:.2f}"
        )


if __name__ == "__main__":
    scanner = PreBreakoutScanner(max_assets=200)
    results = scanner.run()
    print_pre_breakout_results(results)