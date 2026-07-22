from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, List

# Ensure CSS project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer

SCAN_INTERVAL = 20
MIN_SIGNAL_STRENGTH = 0.65


class CSSTradingEngine:
    """
    Non-authoritative advisory scanner shell (NOT the paper trading authority).

    Current purpose:
    - scan market
    - score opportunities
    - filter for institutional-grade setups only

    This shell does not dispatch orders, journal fills, or own paper/live
    execution. Canonical paper execution authority is
    ``CanonicalExecutionIntegration`` backed by the validation-only
    ``UnifiedExecutionPipeline`` (see
    ``docs/governance/CSS_PAPER_TRADING_AUTHORITY.md``).
    """

    AUTHORITATIVE_PAPER_ENGINE = False

    def __init__(self) -> None:
        self.scanner = UnifiedMarketScanner()
        self.scorer = AIOpportunityScorer()

        self.capital = 250.0
        self.reserve = 25.0

    def scan_market(self) -> List[Dict]:
        assets = self.scanner.scan()
        opportunities: List[Dict] = []

        for asset in assets:
            symbol = str(
                asset.get("symbol")
                or asset.get("product_id")
                or asset.get("asset")
                or "UNKNOWN"
            )

            try:
                score = float(self.scorer.score_opportunity(asset))
            except Exception:
                score = 0.0

            opportunity = {
                "symbol": symbol,
                "score": score,
                "price": asset.get("price"),
                "regime": asset.get("regime", "UNKNOWN"),
                "strategy": asset.get("regime", "UNKNOWN"),
                "asset": asset,
            }

            opportunities.append(opportunity)

        opportunities.sort(key=lambda x: x["score"], reverse=True)
        return opportunities

    def filter_institutional_signals(self, opportunities: List[Dict]) -> List[Dict]:
        filtered: List[Dict] = []

        for opp in opportunities:
            score = float(opp.get("score", 0.0))

            if score < MIN_SIGNAL_STRENGTH:
                continue

            filtered.append(opp)

        return filtered

    def run(self) -> None:
        print("\nCSS Trading Engine started\n")

        while True:
            try:
                print(f"Next scan in {SCAN_INTERVAL} seconds...\n")

                opportunities = self.scan_market()

                print(f"{len(opportunities)} trade opportunities detected")

                filtered = self.filter_institutional_signals(opportunities)

                if not filtered:
                    print("No institutional-grade opportunities detected")
                    time.sleep(SCAN_INTERVAL)
                    continue

                deployable = self.capital - self.reserve
                capital_per_trade = deployable / len(filtered)

                print("\nCapital allocations:")

                for opp in filtered:
                    print(
                        f"{opp['symbol']} | "
                        f"ai_score={opp['score']:.2f} | "
                        f"capital={capital_per_trade:.2f}"
                    )

            except KeyboardInterrupt:
                print("\nCSS Trading Engine stopped by user.")
                break
            except Exception as e:
                print("ENGINE ERROR:", e)

            time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    engine = CSSTradingEngine()
    engine.run()