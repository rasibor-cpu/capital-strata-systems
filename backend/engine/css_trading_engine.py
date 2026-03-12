from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)
from backend.strategies.range_mean_reversion import range_mean_reversion_signal
from backend.execution.coinbase_executor import CoinbaseExecutor

try:
    from backend.scanner.coinbase_universe import get_top_universe
except Exception:
    get_top_universe = None


class CSSTradingEngine:
    """
    CSS Trading Engine

    Multi-regime execution controller:
    - TREND  -> VWAP trend / mean reversion trigger path
    - RANGE  -> range mean reversion strategy
    - other  -> no trade

    Safe by design:
    - scoring first
    - allocation second
    - risk approval before execution
    """

    def __init__(self) -> None:
        self.scorer = AIOpportunityScorer()
        self.allocator = CapitalAllocator()
        self.risk_governor = PortfolioRiskGovernor()
        self.executor = CoinbaseExecutor()

        self.scan_interval_seconds = int(os.getenv("CSS_SCAN_INTERVAL_SECONDS", "20"))
        self.max_assets = int(os.getenv("CSS_MAX_ASSETS", "4"))
        self.reserve_ratio = float(os.getenv("CSS_RESERVE_RATIO", "0.10"))
        self.max_asset_fraction = float(os.getenv("CSS_MAX_ASSET_FRACTION", "0.40"))
        self.starting_gross_capital = float(os.getenv("CSS_STARTING_GROSS_CAPITAL", "250"))

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_universe(self) -> List[Dict[str, Any]]:
        if get_top_universe is None:
            return []

        try:
            assets = get_top_universe(limit=self.max_assets)
            if not assets:
                return []
            if isinstance(assets, list):
                return assets
            return []
        except Exception as exc:
            print(f"UNIVERSE ERROR: {exc}")
            return []

    def _extract_price_and_vwap(self, asset: Dict[str, Any]) -> Tuple[float | None, float | None]:
        price = asset.get("price")
        vwap = asset.get("vwap")

        candles = asset.get("candles", [])
        if vwap is None and candles:
            try:
                cfg = VWAPConfig()
                vwap = compute_vwap_from_candles(candles, cfg)
            except Exception:
                vwap = None

        try:
            price = float(price) if price is not None else None
        except Exception:
            price = None

        try:
            vwap = float(vwap) if vwap is not None else None
        except Exception:
            vwap = None

        return price, vwap

    def _build_strategy_payload(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        price, vwap = self._extract_price_and_vwap(asset)

        payload = {
            "symbol": asset.get("symbol") or asset.get("product_id") or asset.get("asset") or "UNKNOWN",
            "price": price,
            "vwap": vwap,
            "regime": str(asset.get("regime", "")).upper(),
            "volatility": float(asset.get("volatility", 0) or 0),
            "trend_efficiency": float(asset.get("trend_efficiency", 0) or 0),
            "raw_asset": asset,
        }
        return payload

    def _strategy_decision(self, asset: Dict[str, Any]) -> Tuple[bool, str]:
        payload = self._build_strategy_payload(asset)
        regime = payload["regime"]

        if regime == "RANGE":
            allowed = range_mean_reversion_signal(payload)
            return allowed, "RANGE_MEAN_REVERSION"

        allowed = should_buy_mean_reversion(asset)
        return bool(allowed), "TREND_VWAP"

    def _print_capital_snapshot(self) -> Dict[str, float]:
        gross = self.starting_gross_capital
        reserve = round(gross * self.reserve_ratio, 2)
        deployable = round(gross - reserve, 2)
        asset_limit = round(deployable * self.max_asset_fraction, 2)

        print(
            f"Capital snapshot: gross={gross:.2f} | "
            f"reserve={reserve:.2f} | "
            f"deployable={deployable:.2f} | "
            f"asset_limit={asset_limit:.2f}"
        )

        return {
            "gross": gross,
            "reserve": reserve,
            "deployable": deployable,
            "asset_limit": asset_limit,
        }

    def _score_and_rank(self, assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        opportunities: List[Dict[str, Any]] = []

        for asset in assets:
            symbol = asset.get("symbol") or asset.get("product_id") or asset.get("asset") or "UNKNOWN"

            try:
                strategy_ok, strategy_name = self._strategy_decision(asset)
            except Exception as exc:
                print(f"STRATEGY ERROR: {symbol} | {exc}")
                continue

            if not strategy_ok:
                continue

            try:
                score = float(self.scorer.score_opportunity(asset))
            except Exception:
                score = 0.0

            opportunities.append(
                {
                    "symbol": symbol,
                    "strategy": strategy_name,
                    "ai_score": score,
                    "asset": asset,
                }
            )

        opportunities.sort(key=lambda x: x["ai_score"], reverse=True)
        return opportunities

    def _allocate_capital(
        self,
        ranked: List[Dict[str, Any]],
        capital_state: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        if not ranked:
            return []

        deployable = capital_state["deployable"]
        asset_limit = capital_state["asset_limit"]

        allocation_count = min(len(ranked), 4)
        if allocation_count <= 0:
            return []

        equal_share = round(deployable / allocation_count, 2)

        allocated: List[Dict[str, Any]] = []
        for item in ranked[:allocation_count]:
            capital = min(equal_share, asset_limit)
            item["capital"] = round(capital, 2)
            allocated.append(item)

        return allocated

    def _execute_best_candidate(self, candidates: List[Dict[str, Any]]) -> None:
        if not candidates:
            print("No executable candidates after allocation.")
            return

        best = candidates[0]
        symbol = best["symbol"]
        capital = float(best["capital"])
        asset = best["asset"]

        try:
            decision = self.risk_governor.approve_trade(best, capital)
        except Exception as exc:
            print(f"RISK GOVERNOR ERROR: {symbol} | {exc}")
            return

        final_decision = str(decision.get("final_decision", "BLOCK")).upper()
        if final_decision != "ALLOW":
            print(f"RISK BLOCK: {symbol} | final_decision={final_decision}")
            return

        try:
            result = self.executor.execute_trade(
                asset=symbol,
                allocation=capital,
                decision_envelope=decision,
            )
            print(f"EXECUTED: {symbol} | strategy={best['strategy']} | capital={capital:.2f}")
            print(result)
        except Exception as exc:
            print(f"EXECUTION ERROR: {symbol} | {exc}")

    def run(self) -> None:
        print("CSS Trading Engine started.")
        choose_session_policy()

        while True:
            try:
                print()
                print(f"Next scan in {self.scan_interval_seconds} seconds...")
                print()

                capital_state = self._print_capital_snapshot()
                assets = self._load_universe()

                if not assets:
                    print("No assets returned by scanner.")
                    time.sleep(self.scan_interval_seconds)
                    continue

                ranked = self._score_and_rank(assets)
                print(f"{len(ranked)} trade opportunities detected")
                print()

                if ranked:
                    allocated = self._allocate_capital(ranked, capital_state)

                    print("Capital allocations:")
                    for item in allocated:
                        print(
                            f"  {item['symbol']} | "
                            f"strategy={item['strategy']} | "
                            f"ai_score={item['ai_score']:.2f} | "
                            f"capital={item['capital']:.2f}"
                        )

                    print()
                    self._execute_best_candidate(allocated)
                else:
                    print("No valid strategy-aligned opportunities detected.")

            except KeyboardInterrupt:
                print("\nCSS Trading Engine stopped by user.")
                break
            except Exception as exc:
                print(f"ENGINE LOOP ERROR: {exc}")

            time.sleep(self.scan_interval_seconds)


if __name__ == "__main__":
    engine = CSSTradingEngine()
    engine.run()