from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path so absolute imports work
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scanner.market_scanner import MarketScanner, ScannerConfig
from backend.scanner.fx_market_scanner import OandaFXMarketScanner, FXScannerConfig


@dataclass
class UnifiedScannerConfig:
    enable_crypto: bool = True
    enable_fx: bool = True
    crypto_top_n: int = 5
    fx_top_n: int = 5
    final_top_n: int = 8


class UnifiedMarketScanner:
    """
    CSS Unified Market Scanner

    Combines ranked opportunities from:
    - Coinbase crypto scanner
    - OANDA FX scanner

    Produces a single ranked opportunity list for the engine.
    """

    def __init__(self, config: Optional[UnifiedScannerConfig] = None) -> None:
        self.config = config or UnifiedScannerConfig()

    def scan_crypto(self) -> List[Dict[str, Any]]:
        if not self.config.enable_crypto:
            return []

        scanner = MarketScanner(
            config=ScannerConfig(
                top_n=self.config.crypto_top_n,
                quote_currency="USD",
                candle_granularity_seconds=900,
                lookback_candles=50,
                min_quote_volume_usd=10000.0,
                max_products_to_scan=120,
                vwap_window=20,
            )
        )

        results = scanner.scan_market()
        out: List[Dict[str, Any]] = []
        for r in results:
            out.append(
                {
                    "asset_class": "CRYPTO",
                    "symbol": r.product_id,
                    "score": float(r.score),
                    "last_price": float(r.last_price),
                    "spread_pct": float(r.spread_pct),
                    "volatility_pct": float(r.volatility_pct),
                    "trend_pct": float(r.trend_pct),
                    "source": "Coinbase",
                }
            )
        return out

    def scan_fx(self) -> List[Dict[str, Any]]:
        if not self.config.enable_fx:
            return []

        scanner = OandaFXMarketScanner(
            config=FXScannerConfig(
                top_n=self.config.fx_top_n,
                granularity="M15",
                count=60,
                min_avg_range_pct=0.0001,
                min_abs_spread_from_vwap_pct=0.00001,
                vwap_window=20,
                debug=False,
            )
        )

        results = scanner.scan_market()
        out: List[Dict[str, Any]] = []
        for r in results:
            out.append(
                {
                    "asset_class": "FX",
                    "symbol": r.instrument,
                    "score": float(r.score),
                    "last_price": float(r.last_mid),
                    "spread_pct": float(r.spread_from_vwap_pct),
                    "volatility_pct": float(r.volatility_pct),
                    "trend_pct": float(r.trend_pct),
                    "source": "OANDA",
                }
            )
        return out

    def scan_all(self) -> List[Dict[str, Any]]:
        combined: List[Dict[str, Any]] = []
        combined.extend(self.scan_crypto())
        combined.extend(self.scan_fx())

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[: self.config.final_top_n]


def print_unified_results(results: List[Dict[str, Any]]) -> None:
    print("\n=== CSS UNIFIED MARKET SCANNER ===")
    if not results:
        print("No qualifying opportunities found.")
        return

    for i, r in enumerate(results, start=1):
        print(
            f"{i:>2}. [{r['asset_class']}] {r['symbol']:<12} "
            f"score={r['score']:>8.4f}   "
            f"spread={r['spread_pct']:>9.6f}%   "
            f"vol={r['volatility_pct']:>8.6f}%   "
            f"trend={r['trend_pct']:>9.6f}%   "
            f"src={r['source']}"
        )


if __name__ == "__main__":
    scanner = UnifiedMarketScanner(
        config=UnifiedScannerConfig(
            enable_crypto=True,
            enable_fx=True,
            crypto_top_n=5,
            fx_top_n=5,
            final_top_n=8,
        )
    )

    results = scanner.scan_all()
    print_unified_results(results)

    print("\nTop symbols only:")
    for item in results:
        print(f"{item['asset_class']} | {item['symbol']}")