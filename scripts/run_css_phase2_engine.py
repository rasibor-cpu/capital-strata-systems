from __future__ import annotations

import time

from backend.intelligence.market_intelligence import MarketIntelligenceEngine
from backend.intelligence.strategy_selector import StrategySelector
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.execution.trade_manager import TradeManager


class CSSPhase2Engine:

    def __init__(self):

        self.market_engine = MarketIntelligenceEngine(max_assets=5)

        self.strategy_selector = StrategySelector()

        self.capital_allocator = CapitalAllocator(total_capital=200)

        self.trade_manager = TradeManager()

    def run_cycle(self):

        print("\n====== CSS Phase 2 Engine Cycle ======\n")

        # STEP 1 — Market Intelligence
        ranked_assets = self.market_engine.get_top_assets()

        print("Top Assets Selected:")
        print(ranked_assets)

        # STEP 2 — Strategy Selection
        print("\nStrategy Selection")

        strategies = {}

        for asset in ranked_assets:

            decision = self.strategy_selector.select_strategy(asset)

            strategies[asset] = decision.strategy

            print(
                f"{asset:10} Regime:{decision.regime:10} Strategy:{decision.strategy}"
            )

        # STEP 3 — Capital Allocation
        print("\nCapital Allocation")

        allocations = self.capital_allocator.allocate(ranked_assets)

        for alloc in allocations:

            print(
                f"{alloc.asset:10} Capital:${alloc.allocation_usd}"
            )

        # STEP 4 — Open Simulated Positions
        print("\nOpening Positions")

        for alloc in allocations:

            entry_price = 100  # placeholder

            size = alloc.allocation_usd / entry_price

            self.trade_manager.open_position(
                alloc.asset,
                entry_price,
                size
            )

        print("\nPositions Opened")


def main():

    engine = CSSPhase2Engine()

    while True:

        engine.run_cycle()

        print("\nNext scan in 20 seconds...\n")

        time.sleep(20)


if __name__ == "__main__":

    main()