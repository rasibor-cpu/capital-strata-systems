from __future__ import annotations

import concurrent.futures
from typing import List, Dict

from backend.scanner.coinbase_universe import get_top_universe
from backend.data.coinbase_historical_downloader import load_runtime_asset


class UnifiedMarketScanner:
    """
    CSS Unified Market Scanner

    Responsibilities
    ----------------
    1. Discover tradable symbols
    2. Load runtime asset data
    3. Run scans in parallel
    """

    def __init__(self, max_workers: int = 8):

        self.max_workers = max_workers

    def discover_symbols(self) -> List[str]:

        try:
            symbols = get_top_universe(20)
        except Exception:
            symbols = []

        return symbols

    def build_assets(self, symbols: List[str]) -> List[Dict]:

        assets: List[Dict] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = [
                executor.submit(load_runtime_asset, symbol)
                for symbol in symbols
            ]

            for future in concurrent.futures.as_completed(futures):

                try:

                    asset = future.result()

                    if asset and asset.get("price"):

                        assets.append(asset)

                except Exception:
                    pass

        return assets

    def scan(self) -> List[Dict]:

        symbols = self.discover_symbols()

        if not symbols:
            return []

        assets = self.build_assets(symbols)

        return assets