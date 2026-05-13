from __future__ import annotations

from typing import Dict, Any, List

from backend.intelligence.scanner_coordinator import ScannerCoordinator
from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
from backend.intelligence.adaptive_exit_engine import AdaptiveExitEngine


class IntelligenceOrchestrator:
    """
    CSS Intelligence Orchestrator

    Coordinates all intelligence modules:
    - Market Scanner
    - Trade Decision Engine
    - Adaptive Exit Engine
    """

    def __init__(self) -> None:

        self.scanner = ScannerCoordinator()
        self.trade_engine = TradeDecisionOrchestrator()
        self.exit_engine = AdaptiveExitEngine()

    def discover_opportunities(
        self,
        market_data: Dict[str, Dict[str, Any]],
    ) -> List[str]:

        return self.scanner.best_assets(market_data)

    def evaluate_trade(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        return self.trade_engine.evaluate_trade(
            {
                "symbol": symbol,
                "candles": candles,
            }
        )

    def evaluate_exit(
        self,
        entry_price: float,
        candles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        return self.exit_engine.evaluate_exit(entry_price, candles)


if __name__ == "__main__":

    orchestrator = IntelligenceOrchestrator()

    example_market = {
        "EUR_USD": {"asset_class": "forex", "candles": []},
        "BTC_USD": {"asset_class": "crypto", "candles": []},
    }

    assets = orchestrator.discover_opportunities(example_market)

    print("Best assets:", assets)
