from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.execution.coinbase_executor import CoinbaseExecutor, OrderIntent
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    should_buy_mean_reversion,
)
from backend.strategies.range_mean_reversion import (
    range_mean_reversion_signal,
)
from backend.scanner.coinbase_universe import get_top_universe
from backend.data.coinbase_historical_downloader import load_runtime_universe


class CSSTradingEngine:
    """
    Capital Strata Systems Trading Engine

    Current live path:
    scanner -> runtime loader -> scorer -> allocator -> risk governor -> executor

    Notes:
    - Coinbase is the active provider path for now.
    - Architecture should remain easy to refactor into broker/provider adapters later.
    """

    def __init__(self) -> None:
        self.scan_interval = int(os.getenv("CSS_SCAN_INTERVAL_SECONDS", "20"))
        self.max_assets = int(os.getenv("CSS_MAX_ASSETS", "12"))
        self.total_capital = float(os.getenv("CSS_STARTING_GROSS_CAPITAL", "250"))

        self.reserve_ratio = float(os.getenv("CSS_RESERVE_RATIO", "0.10"))
        self.max_asset_fraction = float(os.getenv("CSS_MAX_ASSET_FRACTION", "0.40"))

        self.scorer = AIOpportunityScorer()
        self.allocator = CapitalAllocator(self.total_capital)
        self.risk_governor = PortfolioRiskGovernor(self.total_capital)
        self.executor = CoinbaseExecutor()
        self.vwap_cfg = VWAPConfig()

    # --------------------------------------------------
    # Capital
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Strategy routing
    # --------------------------------------------------

    def strategy_router(self, asset: Dict[str, Any]) -> Tuple[bool, str]:
        regime = str(asset.get("regime", "")).upper()

        if regime == "RANGE":
            allowed = range_mean_reversion_signal(asset)
            return bool(allowed), "RANGE_MEAN_REVERSION"

        price = asset.get("price")
        vwap = asset.get("vwap")

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

    # --------------------------------------------------
    # Risk decision normalization
    # --------------------------------------------------

    def normalize_risk_decision(self, raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            raw["final_decision"] = str(
                raw.get("final_decision", "BLOCK")
            ).upper()
            return raw

        if isinstance(raw, tuple):
            if len(raw) == 0:
                return {"final_decision": "BLOCK", "reason": "empty tuple"}

            first = raw[0]

            if isinstance(first, bool):
                return {
                    "final_decision": "ALLOW" if first else "BLOCK",
                    "reason": raw[1] if len(raw) > 1 else "",
                }

            if isinstance(first, str):
                text = first.strip().upper()
                return {
                    "final_decision": "ALLOW" if text in {"ALLOW", "APPROVE", "APPROVED", "PASS", "TRUE"} else "BLOCK",
                    "reason": raw[1] if len(raw) > 1 else first,
                }

            if isinstance(first, dict):
                first["final_decision"] = str(
                    first.get("final_decision", "BLOCK")
                ).upper()
                if len(raw) > 1 and "reason" not in first:
                    first["reason"] = raw[1]
                return first

        if isinstance(raw, bool):
            return {
                "final_decision": "ALLOW" if raw else "BLOCK",
                "reason": "boolean risk response",
            }

        return {
            "final_decision": "BLOCK",
            "reason": f"unsupported risk response: {type(raw).__name__}",
        }

    # --------------------------------------------------
    # Execution
    # --------------------------------------------------

    def execute_trade(self, best: Dict[str, Any]) -> None:
        symbol = best["symbol"]
        capital = best["capital"]

        try:
            intent = OrderIntent(
                product_id=symbol,
                side="BUY",
                quote_size=capital,
                order_type="MARKET",
            )

            order = self.executor.create_order(intent)
            print("Trade executed:", order)

        except Exception as e:
            print("Execution error:", e)

    # --------------------------------------------------
    # Main loop
    # --------------------------------------------------

    def run(self) -> None:
        print("\nCSS Trading Engine started\n")

        choose_session_policy(self.total_capital)

        while True:
            try:
                print(f"Next scan in {self.scan_interval} seconds...\n")

                deployable, asset_limit = self.capital_snapshot()

                # Step 1: discover tradable universe
                symbols = get_top_universe(self.max_assets)

                if not symbols:
                    print("Scanner returned no symbols\n")
                    time.sleep(self.scan_interval)
                    continue

                # Step 2: enrich symbols into runtime-ready assets
                universe = load_runtime_universe(symbols)

                if not universe:
                    print("Market loader returned no assets\n")
                    time.sleep(self.scan_interval)
                    continue

                # Step 3: score and filter opportunities
                opportunities = []

                for asset in universe:
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

                # Step 4: allocate capital across top opportunities
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

                # Step 5: risk approval on best candidate
                best = allocations[0]

                raw_decision = self.risk_governor.approve_trade(
                    best["symbol"],
                    best["capital"],
                )

                decision = self.normalize_risk_decision(raw_decision)

                if decision["final_decision"] != "ALLOW":
                    print(
                        f"Risk governor blocked trade"
                        + (
                            f" | reason={decision.get('reason')}"
                            if decision.get("reason")
                            else ""
                        )
                    )
                else:
                    self.execute_trade(best)

            except KeyboardInterrupt:
                print("\nCSS Trading Engine stopped by user.")
                break
            except Exception as e:
                print("ENGINE ERROR:", e)

            time.sleep(self.scan_interval)


if __name__ == "__main__":
    engine = CSSTradingEngine()
    engine.run()