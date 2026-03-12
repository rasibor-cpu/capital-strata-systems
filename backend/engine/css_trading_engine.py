from __future__ import annotations

import time
from typing import List, Dict

from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.strategies.vwap_mean_reversion import (
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

SCAN_INTERVAL = 20

# Institutional signal quality threshold
MIN_SIGNAL_STRENGTH = 0.65


class CSSTradingEngine:

    def __init__(self):

        self.scanner = UnifiedMarketScanner()
        self.scorer = AIOpportunityScorer()

        self.capital = 250
        self.reserve = 25

    def scan_market(self) -> List[Dict]:

        assets = self.scanner.scan()

        opportunities = []

        for asset in assets:

            candles = asset.get("candles")

            if not candles:
                continue

            vwap = compute_vwap_from_candles(candles)

            if vwap is None:
                continue

            mid = asset["price"]

            spread_bps = ((mid - vwap) / vwap) * 10000

            buy_ok, reason = should_buy_mean_reversion(
                mid,
                vwap,
                spread_bps,
                None,
            )

            if not buy_ok:
                continue

            opportunity = {
                "symbol": asset["symbol"],
                "price": mid,
                "spread_bps": spread_bps,
                "volatility": asset.get("volatility", 0),
                "regime": asset.get("regime", "RANGE"),
            }

            score = self.scorer.score_opportunity(opportunity)

            opportunity["score"] = score["score"]

            opportunities.append(opportunity)

        return opportunities

    def filter_institutional_signals(self, opportunities):

        filtered = []

        for opp in opportunities:

            score = float(opp.get("score", 0))

            if score < MIN_SIGNAL_STRENGTH:
                continue

            filtered.append(opp)

        return filtered

    def run(self):

        print("\nCSS Trading Engine started\n")

        while True:

            print("\nNext scan in 20 seconds...\n")

            time.sleep(SCAN_INTERVAL)

            opportunities = self.scan_market()

            print(f"{len(opportunities)} trade opportunities detected")

            opportunities = self.filter_institutional_signals(opportunities)

            if not opportunities:

                print("No institutional-grade opportunities detected")

                continue

            deployable = self.capital - self.reserve

            capital_per_trade = deployable / len(opportunities)

            print("\nCapital allocations:")

            for opp in opportunities:

                print(
                    f"{opp['symbol']} | ai_score={opp['score']:.2f} | capital={capital_per_trade:.2f}"
                )


if __name__ == "__main__":

    engine = CSSTradingEngine()

    engine.run()