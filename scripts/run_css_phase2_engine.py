from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.execution.trade_manager import TradeManager
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.market_intelligence import MarketIntelligenceEngine
from backend.intelligence.strategy_selector import StrategySelector
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor


class CSSPhase2Engine:
    def __init__(self) -> None:
        self.total_capital = 200.0
        self.market_engine = MarketIntelligenceEngine(max_assets=5)
        self.strategy_selector = StrategySelector()
        self.capital_allocator = CapitalAllocator(total_capital=self.total_capital)
        self.trade_manager = TradeManager()
        self.risk_governor = PortfolioRiskGovernor(
            max_open_positions=5,
            max_asset_allocation_pct=0.40,
            max_total_deployed_pct=1.00,
            total_capital=self.total_capital,
        )

    def run_cycle(self) -> None:
        print("\n====== CSS Phase 2 Engine Cycle ======\n")

        ranked_assets = self.market_engine.get_top_assets()

        print("Top Assets Selected:")
        print(ranked_assets)

        print("\nStrategy Selection")
        strategies: dict[str, str] = {}

        for asset in ranked_assets:
            decision = self.strategy_selector.select_strategy(asset)
            strategies[asset] = decision.strategy
            print(
                f"{asset:10} Regime:{decision.regime:10} Strategy:{decision.strategy}"
            )

        print("\nCapital Allocation")
        allocations = self.capital_allocator.allocate(ranked_assets)

        for alloc in allocations:
            print(f"{alloc.asset:10} Capital:${alloc.allocation_usd}")

        print("\nPortfolio Risk Review")
        proposed_batch = [(alloc.asset, alloc.allocation_usd) for alloc in allocations]
        risk_decisions = self.risk_governor.review_batch(
            proposed_allocations=proposed_batch,
            open_positions=self.trade_manager.positions,
        )

        for asset, risk_decision in risk_decisions.items():
            print(
                f"{asset:10} Allowed:{risk_decision.allowed} "
                f"Reason:{risk_decision.reason}"
            )

        print("\nOpening Positions")
        opened_any = False

        for alloc in allocations:
            risk_decision = risk_decisions[alloc.asset]
            if not risk_decision.allowed:
                print(f"Skipped {alloc.asset}: {risk_decision.reason}")
                continue

            entry_price = 100.0
            size = alloc.allocation_usd / entry_price

            self.trade_manager.open_position(
                alloc.asset,
                entry_price,
                size,
            )
            opened_any = True

        if not opened_any:
            print("No new positions opened this cycle.")

        print("\nOpen Position Summary")
        if self.trade_manager.positions:
            for asset, pos in self.trade_manager.positions.items():
                print(
                    f"{asset:10} entry={pos.entry_price:.2f} "
                    f"size={pos.size:.4f} "
                    f"tp1={pos.tp1:.2f} "
                    f"tp2={pos.tp2:.2f} "
                    f"trail={pos.trailing_stop:.2f}"
                )
        else:
            print("No open positions.")

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