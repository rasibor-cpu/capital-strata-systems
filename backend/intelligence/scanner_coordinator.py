from __future__ import annotations

from typing import Dict, Any, List
from backend.intelligence.global_market_scanner import GlobalMarketScanner


class ScannerCoordinator:
    """
    CSS Scanner Coordinator

    This module orchestrates all scanning modules and
    determines the best trading opportunities across markets.
    """

    def __init__(self) -> None:
        self.scanner = GlobalMarketScanner(top_n=5)

    def scan(self, market_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run the global market scanner and return ranked opportunities.
        """

        results = self.scanner.scan_to_dicts(market_data)

        ranked = sorted(
            results,
            key=lambda x: x["score"],
            reverse=True,
        )

        return ranked

    def best_assets(self, market_data: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Return the symbols of the best assets to trade.
        """

        ranked = self.scan(market_data)

        return [asset["symbol"] for asset in ranked]


if __name__ == "__main__":

    example_market = {
        "EUR_USD": {"asset_class": "forex", "candles": []},
        "BTC_USD": {"asset_class": "crypto", "candles": []},
        "SPX500": {"asset_class": "index", "candles": []},
        "XAU_USD": {"asset_class": "commodity", "candles": []},
    }

    coordinator = ScannerCoordinator()

    best = coordinator.best_assets(example_market)

    print("Top Assets:", best)