from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.intelligence.opportunity_router import OpportunityRouter


class CSSTradingEngine:
    """
    CSS Autonomous Trading Engine

    Runs the full pipeline:

    scanner -> scoring -> routing -> paper execution
    """

    def __init__(self) -> None:
        self.router = OpportunityRouter()
        self.crypto_executor = CoinbaseExecutor()
        self.scan_interval_seconds = 20
        self.default_quote_size = 50.0
        self.default_take_profit_pct = 0.02
        self.default_stop_loss_pct = 0.01

    def run(self) -> None:
        print("\n=== CSS TRADING ENGINE STARTED ===\n")

        while True:
            try:
                opportunities = self.router.route()

                if not opportunities:
                    print("No qualifying trades this cycle.")
                else:
                    print(f"\n{len(opportunities)} trade opportunities detected\n")

                    for op in opportunities:
                        self._process_opportunity(op)

                print(f"\nNext scan in {self.scan_interval_seconds} seconds...\n")
                time.sleep(self.scan_interval_seconds)

            except Exception as e:
                print("\nENGINE ERROR:", str(e))
                time.sleep(10)

    def _process_opportunity(self, opportunity: Dict[str, Any]) -> None:
        symbol = str(opportunity.get("symbol", "UNKNOWN"))
        asset_class = str(opportunity.get("asset_class", "UNKNOWN")).upper()
        strategy = str(opportunity.get("strategy", "unknown_strategy"))
        score = self._to_float(opportunity.get("score"), 0.0)

        print(
            f"Executing: {symbol} | "
            f"class={asset_class} | "
            f"strategy={strategy} | "
            f"score={score:.4f}"
        )

        if asset_class == "CRYPTO":
            self._execute_crypto_trade(
                symbol=symbol,
                strategy=strategy,
                confidence=score,
            )
            return

        if asset_class == "FX":
            print(f"FX execution path not yet enabled for {symbol}. Skipping.")
            return

        print(f"Unsupported asset class for {symbol}: {asset_class}. Skipping.")

    def _execute_crypto_trade(
        self,
        symbol: str,
        strategy: str,
        confidence: float,
    ) -> None:
        quote_size = self._determine_quote_size(confidence)

        intent = OrderIntent(
            product_id=symbol,
            side="BUY",
            quote_size=quote_size,
            take_profit_pct=self.default_take_profit_pct,
            stop_loss_pct=self.default_stop_loss_pct,
            strategy=strategy,
            confidence=confidence,
            order_type="MARKET",
        )

        result = self.crypto_executor.create_order(intent)

        fill_price = self._to_float(result.get("fill_price"), 0.0)
        base_size = self._to_float(result.get("base_size"), 0.0)
        status = str(result.get("status", "UNKNOWN"))

        print(
            f"ORDER RESULT: {symbol} | "
            f"status={status} | "
            f"fill_price={fill_price:.8f} | "
            f"base_size={base_size:.8f} | "
            f"quote_size={quote_size:.2f}"
        )

    def _determine_quote_size(self, confidence: float) -> float:
        """
        Simple confidence-based sizing for paper mode.
        Can later be replaced by CapitalAllocator / RiskGovernor logic.
        """
        if confidence >= 0.85:
            return 75.0
        if confidence >= 0.75:
            return 60.0
        return self.default_quote_size

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default


if __name__ == "__main__":
    engine = CSSTradingEngine()
    engine.run()