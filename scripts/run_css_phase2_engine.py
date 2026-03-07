from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so "backend" imports work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.market_intelligence import MarketIntelligenceEngine
from backend.intelligence.strategy_selector import StrategySelector
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.execution.trade_manager import TradeManager


class CSSPhase2Engine:
    def __init__(self) -> None:
        self.market_engine = MarketIntelligenceEngine(max_assets=5)
        self.strategy_selector = StrategySelector()
        self.capital_allocator = CapitalAllocator(total_capital=200)
        self.trade_manager = TradeManager()

    def run_cycle(self) -> None:
        print("\n====== CSS Phase 2 Engine Cycle ======\n")

        # Step 1: Market intelligence
        ranked_assets = self.market_engine.get_top_assets()
        print("Top Assets Selected:")
        print(ranked_assets)

        # Step 2: Strategy selection
        print("\nStrategy Selection")
        strategies: dict[str, str] = {}

        for asset in ranked_assets:
            decision = self.strategy_selector.select_strategy(asset)
            strategies[asset] = decision.strategy
            print(
                f"{asset:10} Regime:{decision.regime:10} Strategy:{decision.strategy}"
            )

        # Step 3: Capital allocation
        print("\nCapital Allocation")
        allocations = self.capital_allocator.allocate(ranked_assets)

        for alloc in allocations:
            print(f"{alloc.asset:10} Capital:${alloc.allocation_usd}")

        # Step 4: Open simulated positions
        print("\nOpening Positions")
        for alloc in allocations:
            entry_price = 100.0  # placeholder
            size = alloc.allocation_usd / entry_price

            self.trade_manager.open_position(
                alloc.asset,
                entry_price,
                size,
            )

        print("\nPositions Opened")

    def run(self, scan_interval_seconds: int = 20) -> None:
        while True:
            self.run_cycle()
            print(f"\nNext scan in {scan_interval_seconds} seconds...\n")
            time.sleep(scan_interval_seconds)


def main() -> None:
    engine = CSSPhase2Engine()
    engine.run(scan_interval_seconds=20)


if __name__ == "__main__":
    main()