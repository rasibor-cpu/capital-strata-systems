from __future__ import annotations

import math
import time
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

import requests

COINBASE_PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"


@dataclass
class ScannerConfig:
    quote_currency: str = "USD"
    candle_granularity_seconds: int = 900  # 15 minutes
    lookback_candles: int = 50
    min_quote_volume_usd: float = 10000.0
    min_base_volume_units: float = 0.0
    max_products_to_scan: int = 120
    per_request_timeout_seconds: float = 10.0
    top_n: int = 5
    pause_between_requests_seconds: float = 0.08
    vwap_window: int = 20


@dataclass
class ScanResult:
    product_id: str
    score: float
    last_price: float
    vwap: float
    spread_pct: float
    volatility_pct: float
    quote_volume_usd: float
    trend_pct: float
    candles_used: int


class MarketScanner:
    """
    CSS Market Scanner v1

    Scans all available Coinbase USD pairs, computes simple opportunity metrics,
    ranks them, and returns the top N symbols for the strategy engine.

    Core ranking dimensions:
    - Absolute spread from VWAP (mean-reversion opportunity)
    - Recent volatility (movement opportunity)
    - Quote-volume / liquidity
    - Small penalty for very strong trend so we avoid stepping in front of trains
    """

    def __init__(
        self,
        config: Optional[ScannerConfig] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = config or ScannerConfig()
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Capital-Strata-Systems/1.0",
                "Accept": "application/json",
            }
        )

    def get_tradeable_products(self) -> List[str]:
        """
        Pull all Coinbase products and keep only active/tradeable pairs quoted in USD.
        """
        response = self.session.get(
            COINBASE_PRODUCTS_URL,
            timeout=self.config.per_request_timeout_seconds,
        )
        response.raise_for_status()
        raw_products = response.json()

        products: List[str] = []
        for item in raw_products:
            product_id = str(item.get("id", "")).strip()
            quote_currency = str(item.get("quote_currency", "")).strip().upper()
            trading_disabled = bool(item.get("trading_disabled", False))
            status = str(item.get("status", "")).strip().lower()

            if not product_id:
                continue
            if quote_currency != self.config.quote_currency.upper():
                continue
            if trading_disabled:
                continue
            if status not in {"online", ""}:
                continue

            # Keep standard spot pairs such as BTC-USD, ETH-USD, etc.
            if "-" not in product_id:
                continue

            products.append(product_id)

        products = sorted(set(products))
        return products[: self.config.max_products_to_scan]

    def get_candles(self, product_id: str) -> List[Dict[str, float]]:
        """
        Coinbase candles response format:
        [ time, low, high, open, close, volume ]
        Returned newest-first; we normalize to oldest-first.
        """
        url = COINBASE_CANDLES_URL.format(product_id=product_id)
        response = self.session.get(
            url,
            params={"granularity": self.config.candle_granularity_seconds},
            timeout=self.config.per_request_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        candles: List[Dict[str, float]] = []
        for row in data:
            if not isinstance(row, list) or len(row) < 6:
                continue
            ts, low, high, open_, close, volume = row[:6]
            try:
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
            except (TypeError, ValueError):
                continue

        # Coinbase returns newest first; reverse to oldest first
        candles.sort(key=lambda x: x["ts"])
        if len(candles) > self.config.lookback_candles:
            candles = candles[-self.config.lookback_candles :]
        return candles

    def compute_vwap(self, candles: List[Dict[str, float]]) -> Optional[float]:
        if len(candles) < 1:
            return None

        window = candles[-self.config.vwap_window :]
        pv_sum = 0.0
        vol_sum = 0.0

        for c in window:
            typical_price = (c["high"] + c["low"] + c["close"]) / 3.0
            volume = c["volume"]
            pv_sum += typical_price * volume
            vol_sum += volume

        if vol_sum <= 0:
            return None
        return pv_sum / vol_sum

    def compute_volatility_pct(self, candles: List[Dict[str, float]]) -> float:
        closes = [c["close"] for c in candles if c["close"] > 0]
        if len(closes) < 5:
            return 0.0

        returns_pct: List[float] = []
        for i in range(1, len(closes)):
            prev_close = closes[i - 1]
            curr_close = closes[i]
            ret = ((curr_close / prev_close) - 1.0) * 100.0
            returns_pct.append(ret)

        if len(returns_pct) < 2:
            return 0.0

        return float(pstdev(returns_pct))

    def compute_trend_pct(self, candles: List[Dict[str, float]]) -> float:
        closes = [c["close"] for c in candles if c["close"] > 0]
        if len(closes) < 5:
            return 0.0

        first_close = closes[0]
        last_close = closes[-1]
        if first_close <= 0:
            return 0.0

        return ((last_close / first_close) - 1.0) * 100.0

    def compute_quote_volume_usd(self, candles: List[Dict[str, float]]) -> float:
        total_quote_volume = 0.0
        for c in candles:
            typical_price = (c["high"] + c["low"] + c["close"]) / 3.0
            total_quote_volume += typical_price * c["volume"]
        return total_quote_volume

    def score_product(self, product_id: str) -> Optional[ScanResult]:
        candles = self.get_candles(product_id)
        if len(candles) < max(20, self.config.vwap_window):
            return None

        last_price = candles[-1]["close"]
        if last_price <= 0:
            return None

        vwap = self.compute_vwap(candles)
        if vwap is None or vwap <= 0:
            return None

        quote_volume_usd = self.compute_quote_volume_usd(candles)
        base_volume_units = sum(c["volume"] for c in candles)

        if quote_volume_usd < self.config.min_quote_volume_usd:
            return None
        if base_volume_units < self.config.min_base_volume_units:
            return None

        spread_pct = ((last_price / vwap) - 1.0) * 100.0
        volatility_pct = self.compute_volatility_pct(candles)
        trend_pct = self.compute_trend_pct(candles)

        # Liquidity term: compressed scaling to prevent huge products dominating.
        liquidity_score = math.log10(max(quote_volume_usd, 1.0))

        # Penalty for steep absolute trend to avoid blindly fading freight trains.
        trend_penalty = abs(trend_pct) * 0.15

        score = (
            abs(spread_pct) * 0.55
            + volatility_pct * 0.30
            + liquidity_score * 0.15
            - trend_penalty
        )

        return ScanResult(
            product_id=product_id,
            score=round(score, 6),
            last_price=round(last_price, 8),
            vwap=round(vwap, 8),
            spread_pct=round(spread_pct, 6),
            volatility_pct=round(volatility_pct, 6),
            quote_volume_usd=round(quote_volume_usd, 2),
            trend_pct=round(trend_pct, 6),
            candles_used=len(candles),
        )

    def scan_market(self) -> List[ScanResult]:
        products = self.get_tradeable_products()
        results: List[ScanResult] = []

        for idx, product_id in enumerate(products, start=1):
            try:
                result = self.score_product(product_id)
                if result is not None:
                    results.append(result)
            except requests.RequestException:
                # Network hiccup or endpoint issue; skip and continue
                continue
            except Exception:
                # Keep scanner resilient
                continue

            if idx < len(products):
                time.sleep(self.config.pause_between_requests_seconds)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[: self.config.top_n]

    def scan_market_as_dicts(self) -> List[Dict[str, Any]]:
        return [self.result_to_dict(r) for r in self.scan_market()]

    @staticmethod
    def result_to_dict(result: ScanResult) -> Dict[str, Any]:
        return {
            "product_id": result.product_id,
            "score": result.score,
            "last_price": result.last_price,
            "vwap": result.vwap,
            "spread_pct": result.spread_pct,
            "volatility_pct": result.volatility_pct,
            "quote_volume_usd": result.quote_volume_usd,
            "trend_pct": result.trend_pct,
            "candles_used": result.candles_used,
        }


def print_scan_results(results: List[ScanResult]) -> None:
    print("\n=== CSS MARKET SCANNER ===")
    if not results:
        print("No qualifying products found.")
        return

    for i, r in enumerate(results, start=1):
        print(
            f"{i:>2}. {r.product_id:<12} "
            f"score={r.score:>8.4f}   "
            f"spread={r.spread_pct:>8.4f}%   "
            f"vol={r.volatility_pct:>7.4f}%   "
            f"trend={r.trend_pct:>8.4f}%   "
            f"liq=${r.quote_volume_usd:,.0f}"
        )


def get_top_products(top_n: int = 5) -> List[str]:
    config = ScannerConfig(top_n=top_n)
    scanner = MarketScanner(config=config)
    results = scanner.scan_market()
    return [r.product_id for r in results]


if __name__ == "__main__":
    scanner = MarketScanner(
        config=ScannerConfig(
            quote_currency="USD",
            candle_granularity_seconds=900,
            lookback_candles=50,
            min_quote_volume_usd=10000.0,
            max_products_to_scan=120,
            top_n=5,
            vwap_window=20,
        )
    )
    scan_results = scanner.scan_market()
    print_scan_results(scan_results)

    print("\nTop products only:")
    for product_id in [r.product_id for r in scan_results]:
        print(product_id)