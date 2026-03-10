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


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(float(raw))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _load_portfolio() -> Dict[str, Any]:
    if not POSITION_FILE.exists():
        return {"positions": []}

    try:
        payload = json.loads(POSITION_FILE.read_text())
        if not isinstance(payload, dict):
            return {"positions": []}
        if "positions" not in payload or not isinstance(payload["positions"], list):
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

    return [x.strip() for x in _env("CSS_PRODUCTS", "BTC-USD,ETH-USD").split(",") if x.strip()]


def _select_assets(ai_results: List[Dict[str, Any]], fallback: List[str], max_assets: int) -> List[str]:
    selected: List[str] = []

    for item in ai_results:
        if item.get("asset_class") != "CRYPTO":
            continue
        if item.get("signal") != "BUY":
            continue

        symbol = str(item.get("symbol", "")).strip()
        if not symbol.endswith("-USD"):
            continue

        selected.append(symbol)
        if len(selected) >= max_assets:
            break

    return selected if selected else fallback[:max_assets]


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _print_header(policy_name: str, capital: float, scan_interval: int, assets: List[str], cycle_no: int) -> None:
    print("==========================================================================")
    print("                    CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
    print("==========================================================================")
    print(f"Cycle: {cycle_no} | Policy: {policy_name} | Capital: {_fmt_money(capital)} | Refresh: {scan_interval}s")
    if len(assets) > 8:
        preview = ", ".join(assets[:8]) + f" ... ({len(assets)} assets)"
    else:
        preview = ", ".join(assets)
    print(f"Configured Base Assets: {preview}")
    print("Trading Enabled: YES")
    print(f"Timestamp (UTC): {_utc()}")
    print("==========================================================================")
    print()


def _print_positions(positions: List[Dict[str, Any]]) -> None:
    print("OPEN POSITIONS")
    print("--------------------------------------------------------------------------")

    if not positions:
        print("FLAT | No open spot positions")
        print()
        return

    for idx, p in enumerate(positions, start=1):
        print(
            f"{idx} | {p['asset']} | "
            f"Entry: {p['entry']} | "
            f"Qty: {p['qty']} | "
            f"Size: {_fmt_money(float(p['size_usd']))}"
        )

    print()


def _print_watchlist(rows: List[Tuple[str, float, float, float, bool, str]]) -> None:
    print("LIVE COINBASE EXECUTION WATCHLIST")
    print("--------------------------------------------------------------------------")
    print(f"{'Asset':12} {'Mid':>12} {'VWAP':>12} {'Spread(bps)':>12} {'Signal':>8} {'Reason':>16}")
    print("-" * 82)

    if not rows:
        print("No assets processed this cycle.")
        print()
        return

    for asset, mid, vwap, spread, signal, reason in rows:
        print(
            f"{asset:<12} "
            f"{mid:>12.6f} "
            f"{vwap:>12.6f} "
            f"{spread:>12.2f} "
            f"{('BUY' if signal else 'HOLD'):>8} "
            f"{reason[:16]:>16}"
        )

    print()


def _print_ai_panel(ai_results: List[Dict[str, Any]], ai_status: str) -> None:
    print("AI OPPORTUNITY SCANNER")
    print("--------------------------------------------------------------------------")
    print(f"Status: {ai_status}")
    print(f"{'Symbol':12} {'Class':8} {'Signal':8} {'Regime':16} {'AI Score':>8} {'Band':10} {'Priority':14}")
    print("-" * 96)

    if not ai_results:
        print("No AI results available this cycle.")
        print()
        return

    for item in ai_results[:8]:
        print(
            f"{item.get('symbol', ''):<12} "
            f"{item.get('asset_class', ''):<8} "
            f"{item.get('signal', ''):<8} "
            f"{item.get('regime', ''):<16} "
            f"{float(item.get('opportunity_score', 0.0)):>8.2f} "
            f"{str(item.get('confidence_band', '')):<10} "
            f"{str(item.get('action_priority', '')):<14}"
        )

    print("\nTop AI explanations:")
    for item in ai_results[:3]:
        explanation = str(item.get("explanation", ""))
        if explanation:
            print(f"- {explanation}")
    print()


def _print_allocations(allocations: List[Dict[str, Any]], total_capital: float) -> None:
    print("AI CAPITAL ALLOCATION PLAN")
    print("--------------------------------------------------------------------------")
    print(f"{'Rank':4} {'Symbol':12} {'AI Score':>10} {'Capital':>12}")
    print("-" * 44)

    if not allocations:
        print("No allocations produced this cycle.")
        print()
        return

    total = 0.0
    for idx, item in enumerate(allocations, start=1):
        capital = float(item.get("capital", 0.0))
        total += capital
        print(
            f"{idx:<4} "
            f"{str(item.get('symbol', '')):<12} "
            f"{float(item.get('ai_score', 0.0)):>10.2f} "
            f"{_fmt_money(capital):>12}"
        )

    print("-" * 44)
    print(f"Allocated: {_fmt_money(total)} | Portfolio Capital Basis: {_fmt_money(total_capital)}")
    print()


def _run_with_timeout(fn, timeout_seconds: int, *args, **kwargs):
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout_seconds)


def _safe_ai_run(ai: AIOpportunityScorer, timeout_seconds: int) -> Tuple[List[Dict[str, Any]], str]:
    try:
        result = _run_with_timeout(ai.run, timeout_seconds)
        if isinstance(result, list):
            return result, f"OK (timeout {timeout_seconds}s)"
        return [], "AI returned non-list result"
    except FuturesTimeoutError:
        return [], f"AI timeout after {timeout_seconds}s"
    except Exception as exc:
        return [], f"AI error: {exc}"


def _safe_get_candles(
    executor: CoinbaseExecutor,
    asset: str,
    granularity: str,
    timeout_seconds: int,
) -> Tuple[List[Dict[str, Any]], str]:
    try:
        result = _run_with_timeout(executor.get_candles, timeout_seconds, asset, granularity)
        if isinstance(result, list):
            return result, "OK"
        return [], "Non-list candles result"
    except FuturesTimeoutError:
        return [], f"Timeout after {timeout_seconds}s"
    except Exception as exc:
        return [], f"Error: {exc}"


def main() -> None:
    scan_interval = _env_int("CSS_SCAN_INTERVAL_SECONDS", 45)
    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200.0)
    max_assets = _env_int("CSS_DYNAMIC_TOP_N", 5)
    ai_timeout_seconds = _env_int("CSS_AI_TIMEOUT_SECONDS", 20)
    candle_timeout_seconds = _env_int("CSS_CANDLE_TIMEOUT_SECONDS", 15)

    universe = _get_universe()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    policy = choose_session_policy(starting_capital)
    governor = PortfolioRiskGovernor(starting_capital)

    executor = CoinbaseExecutor()

    ai = AIOpportunityScorer()
    allocator = CapitalAllocator(
        total_capital=starting_capital,
        max_positions=max_assets,
    )
    decision_engine = TradeDecisionEngine()

    cycle_no = 0

    while True:
        try:
            cycle_no += 1
            latest_status = ""
            ai_status = ""
            candle_cache: Dict[str, List[Dict[str, Any]]] = {}

            portfolio = _load_portfolio()
            positions = portfolio.get("positions", [])

            print(f"[CSS] Cycle {cycle_no} starting...", flush=True)

            ai_results, ai_status = _safe_ai_run(ai, ai_timeout_seconds)
            print(f"[CSS] AI status: {ai_status}", flush=True)

            active_assets = _select_assets(ai_results, universe, max_assets)
            print(f"[CSS] Active assets: {active_assets}", flush=True)

            rows: List[Tuple[str, float, float, float, bool, str]] = []

            for asset in active_assets:
                print(f"[CSS] Fetching candles for {asset}...", flush=True)
                candles, candle_status = _safe_get_candles(
                    executor,
                    asset,
                    "FIFTEEN_MINUTE",
                    candle_timeout_seconds,
                )

                if candle_status != "OK":
                    print(f"[CSS] Candle fetch failed for {asset}: {candle_status}", flush=True)
                    continue

                if len(candles) < 20:
                    print(f"[CSS] Skipping {asset}: insufficient candles ({len(candles)})", flush=True)
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

            allocations = allocator.allocate(
                ai_results=ai_results,
                market_rows=[
                    {
                        "asset": asset,
                        "mid": mid,
                        "vwap": vwap,
                        "spread_bps": spread,
                    }
                    for asset, mid, vwap, spread, _, _ in rows
                ],
            )

            open_assets = {p["asset"] for p in positions}

            for asset, mid, vwap, spread, signal, reason in rows:
                if len(positions) >= max_assets:
                    latest_status = f"Position cap reached ({max_assets})"
                    break

                if asset in open_assets:
                    continue

                if not signal:
                    continue

                candles = candle_cache.get(asset, [])
                if len(candles) < 20:
                    continue

                decision = decision_engine.evaluate_trade(asset, candles)

                if not decision["execute_trade"]:
                    latest_status = (
                        f"Intelligence block: {asset} | "
                        f"regime={decision['regime_reason']} | "
                        f"confluence={decision['confluence_score']:.2f}"
                    )
                    continue

                alloc_size = 0.0
                for item in allocations:
                    if item.get("symbol") == asset:
                        alloc_size = float(item.get("capital", 0.0))
                        break

                if alloc_size <= 0:
                    latest_status = f"No capital allocated to {asset}"
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
                open_assets.add(asset)

                portfolio["positions"] = positions
                _save_portfolio(portfolio)

                latest_status = f"TRADE ENTERED: {asset} @ {mid:.6f} size {_fmt_money(alloc_size)}"

            _clear()
            _print_header(policy.policy_name, starting_capital, scan_interval, universe, cycle_no)
            _print_positions(positions)
            _print_watchlist(rows)
            _print_ai_panel(ai_results, ai_status)
            _print_allocations(allocations, starting_capital)

            if latest_status:
                print("LATEST STATUS")
                print("--------------------------------------------------------------------------")
                print(latest_status)
                print()

            print(f"Refreshing in {scan_interval} seconds... Press Ctrl+C to stop.", flush=True)
            time.sleep(scan_interval)

        except KeyboardInterrupt:
            print("\nCSS stopped")
            break

        except Exception as exc:
            print("Runner error:", exc, flush=True)
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()