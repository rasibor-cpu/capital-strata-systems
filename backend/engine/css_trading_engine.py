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

from backend.strategies.range_mean_reversion import (
    range_mean_reversion_signal,
)

from backend.scanner.coinbase_universe import get_top_universe
from backend.data.coinbase_historical_downloader import load_runtime_universe


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

    def normalize_risk_decision(self, raw_decision: Any) -> Dict[str, Any]:
        if isinstance(raw_decision, dict):
            final_decision = str(raw_decision.get("final_decision", "BLOCK")).upper()
            return {
                "final_decision": final_decision,
                **raw_decision,
            }

        if isinstance(raw_decision, bool):
            return {
                "final_decision": "ALLOW" if raw_decision else "BLOCK",
                "reason": "boolean response from risk governor",
            }

        if isinstance(raw_decision, tuple):
            if len(raw_decision) == 0:
                return {
                    "final_decision": "BLOCK",
                    "reason": "empty tuple from risk governor",
                }

            first = raw_decision[0]

            if isinstance(first, dict):
                decision = dict(first)
                decision["final_decision"] = str(
                    decision.get("final_decision", "BLOCK")
                ).upper()
                if len(raw_decision) > 1 and "reason" not in decision:
                    decision["reason"] = raw_decision[1]
                return decision

            if isinstance(first, bool):
                return {
                    "final_decision": "ALLOW" if first else "BLOCK",
                    "reason": raw_decision[1] if len(raw_decision) > 1 else "tuple bool response",
                }

            if isinstance(first, str):
                text = first.upper().strip()
                if text in {"ALLOW", "APPROVE", "APPROVED", "PASS", "TRUE"}:
                    final = "ALLOW"
                else:
                    final = "BLOCK"

                return {
                    "final_decision": final,
                    "reason": raw_decision[1] if len(raw_decision) > 1 else first,
                }

        return {
            "final_decision": "BLOCK",
            "reason": f"unsupported risk governor response type: {type(raw_decision).__name__}",
        }

    # --------------------------------------------------

    def execute_candidate(
        self,
        best: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Any:
        """
        Adapter for different CoinbaseExecutor method names/signatures.
        Tries common execution interfaces safely.
        """

        symbol = best["symbol"]
        capital = best["capital"]
        asset = best["asset"]

        # Method 1: execute_trade(...)
        if hasattr(self.executor, "execute_trade"):
            method = getattr(self.executor, "execute_trade")
            try:
                return method(
                    asset=symbol,
                    allocation=capital,
                    decision_envelope=decision,
                )
            except TypeError:
                pass

        # Method 2: execute_order(...)
        if hasattr(self.executor, "execute_order"):
            method = getattr(self.executor, "execute_order")
            try:
                return method(
                    asset=symbol,
                    allocation=capital,
                    decision_envelope=decision,
                )
            except TypeError:
                try:
                    return method(symbol, capital, decision)
                except TypeError:
                    pass

        # Method 3: submit_order(...)
        if hasattr(self.executor, "submit_order"):
            method = getattr(self.executor, "submit_order")
            price = asset.get("price")
            quantity = capital

            try:
                return method(
                    instrument=symbol,
                    side="BUY",
                    quantity=quantity,
                    order_type="MARKET",
                    price=price,
                    decision_envelope=decision,
                )
            except TypeError:
                try:
                    return method(
                        symbol=symbol,
                        side="BUY",
                        quantity=quantity,
                        order_type="MARKET",
                        price=price,
                        decision_envelope=decision,
                    )
                except TypeError:
                    pass

        # Method 4: execute(...)
        if hasattr(self.executor, "execute"):
            method = getattr(self.executor, "execute")
            try:
                return method(
                    asset=symbol,
                    allocation=capital,
                    decision_envelope=decision,
                )
            except TypeError:
                try:
                    return method(symbol, capital, decision)
                except TypeError:
                    pass

        available = [
            name for name in dir(self.executor)
            if not name.startswith("_") and callable(getattr(self.executor, name))
        ]
        raise AttributeError(
            "No supported execution method found on CoinbaseExecutor. "
            f"Available callables: {available}"
        )

    # --------------------------------------------------

    def run(self) -> None:
        print("\nCSS Trading Engine started\n")

        choose_session_policy(self.total_capital)

        while True:
            try:
                print(f"Next scan in {self.scan_interval} seconds...\n")

                deployable, asset_limit = self.capital_snapshot()

                symbols = get_top_universe(limit=self.max_assets)

                if not symbols:
                    print("Scanner returned no symbols\n")
                    time.sleep(self.scan_interval)
                    continue

                universe = load_runtime_universe(symbols)

                if not universe:
                    print("Market loader returned no assets\n")
                    time.sleep(self.scan_interval)
                    continue

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

                raw_decision = self.risk_governor.approve_trade(
                    best["symbol"],
                    best["capital"],
                )

                decision = self.normalize_risk_decision(raw_decision)

                if decision["final_decision"] != "ALLOW":
                    print(
                        f"Risk governor blocked trade | "
                        f"reason={decision.get('reason', 'unspecified')}"
                    )
                else:
                    result = self.execute_candidate(best, decision)
                    print("Trade executed:", result)

            except Exception as e:
                print("ENGINE ERROR:", e)

            time.sleep(self.scan_interval)


if __name__ == "__main__":
    engine = CSSTradingEngine()
    engine.run()