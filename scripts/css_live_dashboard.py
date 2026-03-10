from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.intelligence.capital_allocator import CapitalAllocator
from backend.intelligence.trade_decision_engine import TradeDecisionEngine
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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(float(raw))


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _load_portfolio() -> Dict[str, Any]:
    if not POSITION_FILE.exists():
        return {"positions": []}

    try:
        payload = json.loads(POSITION_FILE.read_text())
        if "positions" not in payload:
            payload["positions"] = []
        return payload
    except Exception:
        return {"positions": []}


def _save_portfolio(portfolio: Dict[str, Any]) -> None:
    POSITION_FILE.write_text(json.dumps(portfolio, indent=2))


def _get_universe() -> List[str]:

    if get_top_universe:
        try:
            universe = get_top_universe(200)
            if universe:
                return universe
        except Exception:
            pass

    return ["BTC-USD", "ETH-USD"]


def _fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def _run_with_timeout(fn, timeout_seconds: int, *args):

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        return future.result(timeout=timeout_seconds)


def _safe_ai_run(ai: AIOpportunityScorer, assets: List[Dict[str, Any]], timeout_seconds: int):

    try:

        result = _run_with_timeout(ai.run, timeout_seconds, assets)

        if isinstance(result, list):
            return result, f"OK (timeout {timeout_seconds}s)"

        return [], "AI returned non-list result"

    except FuturesTimeoutError:

        return [], f"AI timeout after {timeout_seconds}s"

    except Exception as exc:

        return [], f"AI error: {exc}"


def main():

    scan_interval = _env_int("CSS_SCAN_INTERVAL_SECONDS", 45)
    capital = _env_float("CSS_STARTING_CAPITAL_USD", 200)
    max_assets = _env_int("CSS_DYNAMIC_TOP_N", 5)

    ai_timeout = _env_int("CSS_AI_TIMEOUT_SECONDS", 20)
    candle_timeout = _env_int("CSS_CANDLE_TIMEOUT_SECONDS", 15)

    universe = _get_universe()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    policy = choose_session_policy(capital)
    governor = PortfolioRiskGovernor(capital)

    executor = CoinbaseExecutor()

    ai = AIOpportunityScorer()

    allocator = CapitalAllocator(
        total_capital=capital,
        max_positions=max_assets,
    )

    decision_engine = TradeDecisionEngine()

    cycle_no = 0

    while True:

        try:

            cycle_no += 1

            portfolio = _load_portfolio()
            positions = portfolio.get("positions", [])

            rows: List[Tuple[str, float, float, float, bool, str]] = []
            candle_cache = {}

            active_assets = universe[:max_assets]

            for asset in active_assets:

                candles = _run_with_timeout(
                    executor.get_candles,
                    candle_timeout,
                    asset,
                    "FIFTEEN_MINUTE",
                )

                if not candles or len(candles) < 20:
                    continue

                candle_cache[asset] = candles

                vwap = compute_vwap_from_candles(candles, 20)

                mid = float(candles[-1]["close"])

                spread = ((mid - vwap) / vwap) * 10000.0

                signal, reason = should_buy_mean_reversion(
                    mid,
                    vwap,
                    spread,
                    vwap_cfg,
                )

                rows.append((asset, mid, vwap, spread, signal, str(reason)))

            ai_inputs = [

                {
                    "symbol": asset,
                    "asset": asset,
                    "asset_class": "CRYPTO",
                    "signal": "BUY" if signal else "HOLD",
                    "mid": mid,
                    "vwap": vwap,
                    "spread_bps": spread,
                    "regime": "MEAN_REVERSION",
                }

                for asset, mid, vwap, spread, signal, _ in rows

            ]

            ai_results, ai_status = _safe_ai_run(ai, ai_inputs, ai_timeout)

            allocations = allocator.allocate(
                ai_results=ai_results,
                market_rows=[
                    {
                        "asset": asset,
                        "symbol": asset,
                        "mid": mid,
                        "vwap": vwap,
                        "spread_bps": spread,
                    }
                    for asset, mid, vwap, spread, _, _ in rows
                ],
            )

            open_assets = {p["asset"] for p in positions}

            latest_status = ""

            for asset, mid, vwap, spread, signal, reason in rows:

                if asset in open_assets:
                    continue

                if not signal:
                    continue

                candles = candle_cache.get(asset, [])

                decision = decision_engine.evaluate_trade(asset, candles)

                if not decision["execute_trade"]:
                    latest_status = f"Intelligence block: {asset}"
                    continue

                alloc_size = 0.0

                for item in allocations:

                    if item.get("symbol") == asset:
                        alloc_size = float(item.get("capital", 0))
                        break

                if alloc_size <= 0:
                    continue

                approved, msg = governor.approve_trade(asset, alloc_size)

                if not approved:
                    latest_status = f"Risk block: {msg}"
                    continue

                qty = alloc_size / mid

                governor.register_trade(asset, alloc_size)

                new_trade = {
                    "asset": asset,
                    "entry": mid,
                    "qty": qty,
                    "size_usd": alloc_size,
                    "ts": _utc(),
                }

                positions.append(new_trade)

                portfolio["positions"] = positions
                _save_portfolio(portfolio)

                latest_status = f"TRADE ENTERED: {asset}"

            _clear()

            print("==========================================================================")
            print("                    CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
            print("==========================================================================")

            print(
                f"Cycle: {cycle_no} | Policy: {policy.policy_name} | Capital: {_fmt_money(capital)} | Refresh: {scan_interval}s"
            )

            print(f"Configured Base Assets: {', '.join(universe[:8])}")

            print(f"Timestamp (UTC): {_utc()}")

            print("==========================================================================\n")

            print("OPEN POSITIONS")
            print("--------------------------------------------------------------------------")

            if not positions:

                print("FLAT | No open spot positions\n")

            for p in positions:

                print(
                    f"{p['asset']} | Entry {p['entry']} | Qty {p['qty']} | Size {_fmt_money(p['size_usd'])}"
                )

            print("\nLIVE COINBASE EXECUTION WATCHLIST")
            print("--------------------------------------------------------------------------")

            for asset, mid, vwap, spread, signal, reason in rows:

                print(
                    f"{asset:12} {mid:10.4f} {vwap:10.4f} {spread:10.2f} {'BUY' if signal else 'HOLD'}"
                )

            print("\nAI OPPORTUNITY SCANNER")
            print("--------------------------------------------------------------------------")

            print(f"Status: {ai_status}")

            for r in ai_results[:5]:

                print(
                    f"{r.get('symbol')} score={r.get('opportunity_score',0):.2f}"
                )

            print("\nAI CAPITAL ALLOCATION PLAN")
            print("--------------------------------------------------------------------------")

            for i, a in enumerate(allocations):

                print(
                    f"{i+1}. {a.get('symbol')}  {_fmt_money(a.get('capital',0))}"
                )

            if latest_status:

                print("\nLATEST STATUS")
                print("--------------------------------------------------------------------------")

                print(latest_status)

            print(f"\nRefreshing in {scan_interval} seconds...")

            time.sleep(scan_interval)

        except KeyboardInterrupt:

            print("CSS stopped")

            break

        except Exception as exc:

            print("Runner error:", exc)

            time.sleep(scan_interval)


if __name__ == "__main__":

    main()