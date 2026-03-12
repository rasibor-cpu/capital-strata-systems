from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

# --------------------------------------------------
# PROJECT ROOT
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --------------------------------------------------
# IMPORTS
# --------------------------------------------------

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.execution.coinbase_executor import CoinbaseExecutor
from backend.risk.session_policy_loader import choose_session_policy

from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    should_buy_mean_reversion,
)
from backend.strategies.range_mean_reversion import range_mean_reversion_signal

from backend.scanner.coinbase_universe import get_top_universe


class CSSTradingEngine:
    def __init__(self) -> None:
        self.scan_interval = int(os.getenv("CSS_SCAN_INTERVAL_SECONDS", "20"))
        self.max_assets = int(os.getenv("CSS_MAX_ASSETS", "4"))
        self.total_capital = float(os.getenv("CSS_STARTING_GROSS_CAPITAL", "250"))

        self.reserve_ratio = 0.10
        self.max_asset_fraction = 0.40

        self.scorer = AIOpportunityScorer()
        self.allocator = CapitalAllocator(self.total_capital)
        self.risk_governor = PortfolioRiskGovernor(self.total_capital)
        self.executor = CoinbaseExecutor()

        self.vwap_cfg = VWAPConfig()

    def capital_snapshot(self) -> Tuple[float, float]:
        gross = self.total_capital
        reserve = round(gross * self.reserve_ratio, 2)
        deployable = round(gross - reserve, 2)
        asset_limit = round(deployable * self.max_asset_fraction, 2)

        print(
            f"Capital snapshot: gross={gross:.2f} | "
            f"reserve={reserve:.2f} | "
            f"deployable={deployable:.2f} | "
            f"asset_limit={asset_limit:.2f}"
        )

        return deployable, asset_limit

    def normalize_asset(self, asset: Any) -> Dict[str, Any]:
        if isinstance(asset, dict):
            return asset

        if isinstance(asset, str):
            return {
                "symbol": asset,
                "product_id": asset,
                "asset": asset,
                "price": None,
                "vwap": None,
                "regime": "TREND",
                "volatility": 0.0,
                "trend_efficiency": 0.0,
            }

        return {
            "symbol": "UNKNOWN",
            "product_id": "UNKNOWN",
            "asset": "UNKNOWN",
            "price": None,
            "vwap": None,
            "regime": "TREND",
            "volatility": 0.0,
            "trend_efficiency": 0.0,
        }

    def extract_price_vwap(self, asset: Dict[str, Any]) -> Tuple[float | None, float | None]:
        price = asset.get("price")
        vwap = asset.get("vwap")

        try:
            price = float(price) if price is not None else None
        except Exception:
            price = None

        try:
            vwap = float(vwap) if vwap is not None else None
        except Exception:
            vwap = None

        return price, vwap

    def strategy_router(self, asset: Dict[str, Any]) -> Tuple[bool, str]:
        regime = str(asset.get("regime", "")).upper()

        if regime == "RANGE":
            return range_mean_reversion_signal(asset), "RANGE_MEAN_REVERSION"

        price, vwap = self.extract_price_vwap(asset)

        if price is None or vwap is None or vwap == 0:
            return False, "TREND_VWAP"

        spread_bps = ((price - vwap) / vwap) * 10000.0

        allowed, _reason = should_buy_mean_reversion(
            price,
            vwap,
            spread_bps,
            self.vwap_cfg,
        )
        return bool(allowed), "TREND_VWAP"

    def run(self) -> None:
        print("\nCSS Trading Engine started\n")

        choose_session_policy(self.total_capital)

        while True:
            try:
                print(f"Next scan in {self.scan_interval} seconds...\n")

                deployable, asset_limit = self.capital_snapshot()

                universe = get_top_universe(limit=self.max_assets)

                if not universe:
                    print("Scanner returned no assets\n")
                    time.sleep(self.scan_interval)
                    continue

                opportunities = []

                for raw_asset in universe:
                    asset = self.normalize_asset(raw_asset)

                    symbol = (
                        asset.get("symbol")
                        or asset.get("product_id")
                        or asset.get("asset")
                        or "UNKNOWN"
                    )

                    allowed, strategy = self.strategy_router(asset)

                    if not allowed:
                        continue

                    try:
                        score = float(self.scorer.score_opportunity(asset))
                    except Exception:
                        score = 0.0

                    opportunities.append(
                        {
                            "symbol": symbol,
                            "score": score,
                            "strategy": strategy,
                            "asset": asset,
                        }
                    )

                opportunities.sort(key=lambda x: x["score"], reverse=True)

                print(f"{len(opportunities)} trade opportunities detected\n")

                if not opportunities:
                    time.sleep(self.scan_interval)
                    continue

                share = deployable / min(len(opportunities), 4)
                allocations = []

                for opp in opportunities[:4]:
                    capital = min(round(share, 2), asset_limit)
                    opp["capital"] = capital
                    allocations.append(opp)

                print("Capital allocations:")

                for a in allocations:
                    print(
                        f"{a['symbol']} | "
                        f"strategy={a['strategy']} | "
                        f"ai_score={a['score']:.2f} | "
                        f"capital={a['capital']:.2f}"
                    )

                best = allocations[0]

                decision = self.risk_governor.approve_trade(
                    best,
                    best["capital"],
                )

                if decision.get("final_decision") != "ALLOW":
                    print("Risk governor blocked trade")
                else:
                    result = self.executor.execute_trade(
                        asset=best["symbol"],
                        allocation=best["capital"],
                        decision_envelope=decision,
                    )
                    print("Trade executed:", result)

            except Exception as e:
                print("ENGINE ERROR:", e)

            time.sleep(self.scan_interval)


if __name__ == "__main__":
    engine = CSSTradingEngine()
    engine.run()