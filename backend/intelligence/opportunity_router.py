from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scanner.unified_market_scanner import UnifiedMarketScanner
from backend.strategies.market_regime import MarketRegimeDetector


class OpportunityRouter:
    """
    CSS Opportunity Router

    Connects:
    scanner → regime detection → strategy selection
    """

    def __init__(self) -> None:
        self.scanner = UnifiedMarketScanner()
        self.regime_detector = MarketRegimeDetector()

    def select_strategy(self, regime: str) -> str:
        regime = regime.upper()

        if regime == "TREND":
            return "momentum_strategy"

        if regime == "BREAKOUT":
            return "breakout_strategy"

        return "vwap_mean_reversion"

    def route(self) -> List[Dict[str, Any]]:
        opportunities = self.scanner.scan_all()
        routed: List[Dict[str, Any]] = []

        for asset in opportunities:
            regime = self.regime_detector.classify(
                trend_pct=asset["trend_pct"],
                volatility_pct=asset["volatility_pct"],
                vwap_spread_pct=asset["spread_pct"],
            )

            strategy = self.select_strategy(regime.regime)

            routed.append(
                {
                    "asset_class": asset["asset_class"],
                    "symbol": asset["symbol"],
                    "score": asset["score"],
                    "last_price": asset["last_price"],
                    "spread_pct": asset["spread_pct"],
                    "volatility_pct": asset["volatility_pct"],
                    "trend_pct": asset["trend_pct"],
                    "source": asset["source"],
                    "regime": regime.regime,
                    "confidence": regime.confidence,
                    "strategy": strategy,
                }
            )

        return routed


def print_routes(routes: List[Dict[str, Any]]) -> None:
    print("\n=== CSS OPPORTUNITY ROUTER ===\n")

    for r in routes:
        print(
            f"{r['symbol']} | {r['asset_class']} | "
            f"score={r['score']:.4f} | "
            f"regime={r['regime']} | "
            f"strategy={r['strategy']}"
        )


if __name__ == "__main__":
    router = OpportunityRouter()
    routes = router.route()
    print_routes(routes)