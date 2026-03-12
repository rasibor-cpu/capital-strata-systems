from __future__ import annotations

import concurrent.futures
from typing import List, Dict

from backend.scanner.coinbase_universe import get_top_universe
from backend.scanner.runtime_loader import load_runtime_asset


class UnifiedMarketScanner:
    """
    CSS Broker-agnostic market scanner.

    Capable of scanning assets from multiple broker adapters
    in parallel.

    Current adapters:
        - Coinbase
    Future adapters:
        - OANDA
        - Alpaca
        - Questrade
    """

    def __init__(self, max_workers: int = 8):

        self.max_workers = max_workers

    def scan_coinbase(self) -> List[str]:

        try:
            return get_top_universe(20)
        except Exception:
            return []

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
                    result = future.result()
                    if result and result.get("price"):
                        assets.append(result)

                except Exception:
                    pass

        return assets

    def scan(self) -> List[Dict]:

        all_assets: List[Dict] = []

        # Coinbase
        coinbase_symbols = self.scan_coinbase()

        coinbase_assets = self.build_assets(coinbase_symbols)

        all_assets.extend(coinbase_assets)

        return all_assets