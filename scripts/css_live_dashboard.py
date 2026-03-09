from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

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

from backend.execution.coinbase_executor import CoinbaseExecutor

try:
    from backend.scanner.coinbase_universe import get_top_universe
except Exception:
    get_top_universe = None


STATE_DIR = PROJECT_ROOT / "backend" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

POSITION_FILE = STATE_DIR / "spot_position.json"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _load_position():

    if not POSITION_FILE.exists():
        return {"in_position": False}

    try:
        return json.loads(POSITION_FILE.read_text())
    except Exception:
        return {"in_position": False}


def _save_position(p):
    POSITION_FILE.write_text(json.dumps(p, indent=2))


def _get_universe():

    if get_top_universe:

        try:
            return get_top_universe(200)

        except Exception:
            pass

    return ["BTC-USD", "ETH-USD"]


def _select_assets(ai_results, fallback, max_assets):

    selected = []

    for r in ai_results:

        if r["asset_class"] != "CRYPTO":
            continue

        if r["signal"] != "BUY":
            continue

        if not r["symbol"].endswith("-USD"):
            continue

        selected.append(r["symbol"])

        if len(selected) >= max_assets:
            break

    if selected:
        return selected

    return fallback[:max_assets]


def main():

    scan_interval = _env_int("CSS_SCAN_INTERVAL_SECONDS", 45)

    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200)

    max_assets = 5

    universe = _get_universe()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    policy = choose_session_policy(starting_capital)

    governor = PortfolioRiskGovernor(policy)

    executor = CoinbaseExecutor(paper_mode=True)

    ai = AIOpportunityScorer()

    allocator = CapitalAllocator(
        total_capital=starting_capital,
        max_positions=max_assets,
    )

    while True:

        try:

            pos = _load_position()

            ai_results = ai.run()

            active_assets = _select_assets(ai_results, universe, max_assets)

            allocations = allocator.allocate(
                ai_results=ai_results,
                market_rows=[],
            )

            rows = []

            for asset in active_assets:

                candles = executor.get_candles(asset, "FIFTEEN_MINUTE")

                if len(candles) < 20:
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

                rows.append((asset, mid, vwap, spread, signal))

                if pos.get("in_position"):
                    continue

                if not signal:
                    continue

                alloc_size = 0

                for a in allocations:
                    if a["symbol"] == asset:
                        alloc_size = float(a["capital"])
                        break

                if alloc_size <= 0:
                    continue

                approved, msg = governor.approve_trade(asset, alloc_size)

                if not approved:
                    continue

                qty = alloc_size / mid

                governor.register_trade(asset, alloc_size)

                pos = {
                    "in_position": True,
                    "asset": asset,
                    "entry": mid,
                    "qty": qty,
                    "size_usd": alloc_size,
                    "ts": _utc(),
                }

                _save_position(pos)

                print(f"\nTRADE ENTERED: {asset} size ${alloc_size:.2f}")

            _clear()

            print("==========================================================")
            print("CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
            print("==========================================================")
            print("Policy:", policy.policy_name)
            print("Capital:", starting_capital)
            print("Refresh:", scan_interval, "seconds")
            print()

            print("POSITION STATUS")

            if pos.get("in_position"):

                print(
                    "OPEN",
                    pos["asset"],
                    "Entry",
                    pos["entry"],
                    "Qty",
                    pos["qty"],
                )

            else:

                print("FLAT")

            print()

            print("LIVE COINBASE EXECUTION WATCHLIST")

            for r in rows:

                asset, mid, vwap, spread, signal = r

                print(
                    asset,
                    "mid",
                    round(mid, 6),
                    "vwap",
                    round(vwap, 6),
                    "spread",
                    round(spread, 2),
                    "signal",
                    "BUY" if signal else "HOLD",
                )

            print()

            print("AI OPPORTUNITY SCANNER")

            for r in ai_results[:5]:

                print(
                    r["symbol"],
                    r["signal"],
                    r["regime"],
                    r["opportunity_score"],
                )

            print()

            print("AI CAPITAL ALLOCATION PLAN")

            total = 0

            for i, a in enumerate(allocations):

                total += a["capital"]

                print(
                    i + 1,
                    a["symbol"],
                    a["ai_score"],
                    "$" + str(round(a["capital"], 2)),
                )

            print()

            print("Allocated:", round(total, 2))

            print()

            print(
                "Refreshing in",
                scan_interval,
                "seconds... Press Ctrl+C to stop.",
            )

            time.sleep(scan_interval)

        except KeyboardInterrupt:

            print("\nCSS stopped")

            break

        except Exception as e:

            print("Runner error:", e)

            time.sleep(scan_interval)


if __name__ == "__main__":
    main()