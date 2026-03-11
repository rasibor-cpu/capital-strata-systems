from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.execution.coinbase_executor import CoinbaseExecutor
from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.trade_decision_engine import TradeDecisionEngine
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.scanner.market_discovery_engine import MarketDiscoveryEngine
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

STATE_DIR = PROJECT_ROOT / "backend" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

POSITION_FILE = STATE_DIR / "spot_position.json"


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def load_positions():

    if not POSITION_FILE.exists():
        return {"positions": []}

    try:
        return json.loads(POSITION_FILE.read_text())
    except Exception:
        return {"positions": []}


def save_positions(data):
    POSITION_FILE.write_text(json.dumps(data, indent=2))


def fmt_money(x):
    return f"${x:,.2f}"


def main():

    capital = 200.0
    refresh = 45
    max_positions = 3

    scanner = MarketDiscoveryEngine()
    universe = scanner.discover()

    executor = CoinbaseExecutor()

    ai = AIOpportunityScorer()

    allocator = CapitalAllocator(
        total_capital=capital,
        max_positions=max_positions,
    )

    policy = choose_session_policy(capital)

    governor = PortfolioRiskGovernor(
        capital,
        max_asset_exposure=policy.max_asset_pct,
        max_portfolio_exposure=policy.max_capital_deployed_pct,
    )

    decision_engine = TradeDecisionEngine()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    cycle = 0

    while True:

        try:

            cycle += 1

            portfolio = load_positions()
            positions = portfolio.get("positions", [])

            open_assets = {p["asset"] for p in positions}

            rows: List[Dict[str, Any]] = []

            for asset in universe[:30]:

                try:

                    candles = executor.get_candles(asset, "FIFTEEN_MINUTE")

                    if not candles or len(candles) < 20:
                        continue

                    vwap = compute_vwap_from_candles(candles, 20)

                    mid = float(candles[-1]["close"])

                    spread = ((mid - vwap) / vwap) * 10000

                    signal, reason = should_buy_mean_reversion(
                        mid,
                        vwap,
                        spread,
                        vwap_cfg,
                    )

                    rows.append(
                        {
                            "asset": asset,
                            "mid": mid,
                            "vwap": vwap,
                            "spread": spread,
                            "signal": "BUY" if signal else "HOLD",
                            "candles": candles,
                        }
                    )

                except Exception:
                    continue

            ai_results = ai.run(rows)

            allocations = allocator.allocate(ai_results)

            latest_status = ""

            for alloc in allocations:

                asset = alloc["symbol"]

                if asset in open_assets:
                    continue

                size = float(alloc["capital"])

                row = next((r for r in rows if r["asset"] == asset), None)

                if not row:
                    continue

                mid = row["mid"]

                candles = row["candles"]

                decision = decision_engine.evaluate_trade(asset, candles)

                if not decision["execute_trade"]:
                    latest_status = f"Intelligence block: {asset}"
                    continue

                approved, msg = governor.approve_trade(asset, size)

                if not approved:
                    latest_status = f"Risk block: {msg}"
                    continue

                qty = size / mid

                governor.register_trade(asset, size)

                trade = {
                    "asset": asset,
                    "entry": mid,
                    "qty": qty,
                    "size_usd": size,
                    "ts": _utc(),
                }

                positions.append(trade)

                portfolio["positions"] = positions

                save_positions(portfolio)

                latest_status = f"TRADE ENTERED: {asset}"

            _clear()

            print("====================================================================")
            print("             CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
            print("====================================================================")

            print(
                f"Cycle: {cycle} | Policy: {policy.policy_name} | Capital: {fmt_money(capital)} | Refresh: {refresh}s"
            )

            print(f"Timestamp (UTC): {_utc()}")

            print("\nOPEN POSITIONS")
            print("--------------------------------------------------------------------")

            if not positions:
                print("FLAT | No open spot positions")
            else:

                for p in positions:
                    print(
                        f"{p['asset']} | Entry {p['entry']} | Qty {p['qty']} | Size {fmt_money(p['size_usd'])}"
                    )

            print("\nLIVE COINBASE EXECUTION WATCHLIST")
            print("--------------------------------------------------------------------")

            for r in rows[:3]:
                print(
                    f"{r['asset']:12} {r['mid']:10.4f} {r['vwap']:10.4f} {r['spread']:10.2f} {r['signal']}"
                )

            print("\nAI CAPITAL ALLOCATION PLAN")
            print("--------------------------------------------------------------------")

            for i, a in enumerate(allocations):
                print(f"{i+1}. {a['symbol']}  {fmt_money(a['capital'])}")

            if latest_status:
                print("\nLATEST STATUS")
                print("--------------------------------------------------------------------")
                print(latest_status)

            print(f"\nRefreshing in {refresh} seconds...")

            time.sleep(refresh)

        except KeyboardInterrupt:

            print("CSS stopped")

            break

        except Exception as e:

            print("Runner error:", e)

            time.sleep(refresh)


if __name__ == "__main__":

    main()