from __future__ import annotations

import concurrent.futures
from typing import List, Dict, Any

from backend.scanner.coinbase_universe import get_top_universe
from backend.data.coinbase_historical_downloader import load_runtime_asset
from backend.scanner.fx_market_scanner import OandaFXMarketScanner


class UnifiedMarketScanner:
    """
    CSS Unified Market Scanner

    Responsibilities
    ----------------
    1. Discover tradable symbols across supported venues
    2. Load runtime asset data
    3. Run scans in parallel
    4. Return a normalized multi-market asset list

    Current supported venues
    ------------------------
    - Coinbase (crypto)
    - OANDA (FX)

    Design Notes
    ------------
    - Gracefully degrades if OANDA credentials are missing
    - Returns a unified list of dictionaries for downstream strategy/risk logic
    - Keeps backward compatibility with current Coinbase runtime asset structure
    - Uses broader upstream discovery so downstream CSS intelligence can be more selective
    """

    def __init__(
        self,
        max_workers: int = 12,
        coinbase_top_n: int = 60,
        fx_top_n: int = 10,
        enable_crypto: bool = True,
        enable_fx: bool = True,
    ) -> None:
        self.max_workers = max_workers
        self.coinbase_top_n = coinbase_top_n
        self.fx_top_n = fx_top_n
        self.enable_crypto = enable_crypto
        self.enable_fx = enable_fx

    # ---------------------------------------------------------
    # COINBASE DISCOVERY + LOAD
    # ---------------------------------------------------------
    def discover_crypto_symbols(self) -> List[str]:
        if not self.enable_crypto:
            return []

        try:
            symbols = get_top_universe(self.coinbase_top_n)
        except Exception:
            symbols = []

        cleaned: List[str] = []
        seen = set()

        for symbol in symbols:
            s = str(symbol).strip().upper()
            if s and s not in seen:
                cleaned.append(s)
                seen.add(s)

        return cleaned

    def build_crypto_assets(self, symbols: List[str]) -> List[Dict[str, Any]]:
        assets: List[Dict[str, Any]] = []

        if not symbols:
            return assets

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_map = {
                executor.submit(load_runtime_asset, symbol): symbol
                for symbol in symbols
            }

            for future in concurrent.futures.as_completed(future_map):
                symbol = future_map[future]

                try:
                    asset = future.result()

                    if not isinstance(asset, dict):
                        continue

                    price = asset.get("price")
                    if not price:
                        continue

                    normalized = dict(asset)
                    normalized["symbol"] = str(asset.get("symbol", symbol)).upper()
                    normalized["market_type"] = "CRYPTO"
                    normalized["venue"] = "COINBASE"
                    normalized["scanner_source"] = "coinbase_universe"

                    assets.append(normalized)

                except Exception:
                    continue

        # Prefer higher scored assets if score exists.
        # Fall back to simple price presence order otherwise.
        assets.sort(
            key=lambda x: float(x.get("score", 0.0)),
            reverse=True,
        )

        return assets

    # ---------------------------------------------------------
    # OANDA FX DISCOVERY + NORMALIZATION
    # ---------------------------------------------------------
    def build_fx_assets(self) -> List[Dict[str, Any]]:
        if not self.enable_fx:
            return []

        try:
            fx_scanner = OandaFXMarketScanner()
            results = fx_scanner.scan_market()
        except Exception:
            return []

        assets: List[Dict[str, Any]] = []

        for row in results:
            try:
                asset = {
                    "symbol": str(row.instrument).upper(),
                    "price": row.last_mid,
                    "vwap": row.vwap,
                    "spread_pct": row.spread_from_vwap_pct,
                    "volatility_pct": row.volatility_pct,
                    "trend_pct": row.trend_pct,
                    "avg_range_pct": row.avg_range_pct,
                    "score": row.score,
                    "candles_used": row.candles_used,
                    "market_type": "FX",
                    "venue": "OANDA",
                    "scanner_source": "fx_market_scanner",
                }
                assets.append(asset)
            except Exception:
                continue

        assets.sort(
            key=lambda x: float(x.get("score", 0.0)),
            reverse=True,
        )

        return assets[: self.fx_top_n]

    # ---------------------------------------------------------
    # COMBINED SCAN
    # ---------------------------------------------------------
    def scan(self) -> List[Dict[str, Any]]:
        crypto_symbols = self.discover_crypto_symbols()
        crypto_assets = self.build_crypto_assets(crypto_symbols)
        fx_assets = self.build_fx_assets()

        combined = crypto_assets + fx_assets

        combined.sort(
            key=lambda x: float(x.get("score", 0.0)),
            reverse=True,
        )

        return combined