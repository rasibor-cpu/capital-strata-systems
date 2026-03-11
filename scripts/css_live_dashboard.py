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
from backend.trading.profit_capture_engine import ProfitCaptureEngine

STATE_DIR = PROJECT_ROOT / "backend" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

POSITION_FILE = STATE_DIR / "spot_position.json"

MAX_SINGLE_POSITION_PCT = 0.40


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


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


def _fmt_money(v: float) -> str:
    return f"${v:,.2f}"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


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
    try:
        scanner = MarketDiscoveryEngine()
        discovered = scanner.discover()
        if discovered:
            return discovered
    except Exception:
        pass

    return ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "LINK-USD"]


def _compute_candle_volume(candles: List[Dict[str, Any]]) -> float:
    total = 0.0
    for c in candles:
        total += _to_float(c.get("volume"), 0.0)
    return total


def _compute_volatility(candles: List[Dict[str, Any]]) -> float:
    closes = [_to_float(c.get("close"), 0.0) for c in candles]
    closes = [x for x in closes if x > 0]
    if len(closes) < 2:
        return 0.0

    returns: List[float] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        curr = closes[i]
        if prev > 0:
            returns.append((curr - prev) / prev)

    if not returns:
        return 0.0

    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    return variance ** 0.5


def _fallback_allocate(
    ai_results: List[Dict[str, Any]],
    total_capital: float,
    max_positions: int,
) -> List[Dict[str, Any]]:
    if not ai_results:
        return []

    candidates: List[Dict[str, Any]] = []
    for item in ai_results:
        signal = str(item.get("signal", "HOLD")).upper()
        score = float(item.get("opportunity_score", item.get("ai_score", 0.0)) or 0.0)
        symbol = str(item.get("symbol", "")).strip()

        if signal != "BUY":
            continue
        if score <= 0.0:
            continue
        if not symbol:
            continue

        candidates.append({"symbol": symbol, "score": score})

    if not candidates:
        return []

    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:max_positions]

    total_score = sum(x["score"] for x in candidates)
    allocations: List[Dict[str, Any]] = []

    for item in candidates:
        weight = item["score"] / total_score if total_score > 0 else 1.0 / len(candidates)
        capital = total_capital * weight
        capital = min(capital, total_capital * MAX_SINGLE_POSITION_PCT)

        allocations.append(
            {
                "symbol": item["symbol"],
                "ai_score": round(item["score"], 4),
                "capital": round(capital, 2),
            }
        )

    return allocations


def _build_allocations(
    allocator: CapitalAllocator,
    ai_results: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
    capital: float,
    max_assets: int,
) -> List[Dict[str, Any]]:
    try:
        allocations = allocator.allocate(
            ai_results=ai_results,
            market_rows=[
                {
                    "asset": row["asset"],
                    "symbol": row["asset"],
                    "mid": row["mid"],
                    "vwap": row["vwap"],
                    "spread_bps": row["spread_bps"],
                }
                for row in rows
            ],
        )

        if isinstance(allocations, list) and allocations:
            capped: List[Dict[str, Any]] = []
            for item in allocations:
                alloc_cap = min(
                    float(item.get("capital", 0.0)),
                    capital * MAX_SINGLE_POSITION_PCT,
                )
                new_item = dict(item)
                new_item["capital"] = round(alloc_cap, 2)
                capped.append(new_item)
            return capped

    except Exception:
        pass

    return _fallback_allocate(ai_results, capital, max_assets)


def main() -> None:
    scan_interval = _env_int("CSS_SCAN_INTERVAL_SECONDS", 45)
    capital = _env_float("CSS_STARTING_CAPITAL_USD", 200.0)
    max_positions = _env_int("CSS_DYNAMIC_TOP_N", 3)
    seed_assets = _env_int("CSS_SEED_ASSET_COUNT", 50)

    universe = _get_universe()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    policy = choose_session_policy(capital)

    governor = PortfolioRiskGovernor(
        capital,
        max_asset_exposure=policy.max_asset_pct,
        max_portfolio_exposure=policy.max_capital_deployed_pct,
    )

    executor = CoinbaseExecutor()
    ai = AIOpportunityScorer()
    allocator = CapitalAllocator(
        total_capital=capital,
        max_positions=max_positions,
    )
    decision_engine = TradeDecisionEngine()
    profit_engine = ProfitCaptureEngine(
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    cycle_no = 0

    while True:
        try:
            cycle_no += 1

            portfolio = _load_portfolio()
            positions = portfolio.get("positions", [])
            open_assets = {p["asset"] for p in positions}

            latest_status = ""
            closed_messages: List[str] = []

            # 1. MANAGE OPEN POSITIONS FIRST
            remaining_positions: List[Dict[str, Any]] = []

            for trade in positions:
                asset = str(trade["asset"])
                entry = float(trade["entry"])
                qty = float(trade["qty"])
                size_usd = float(trade["size_usd"])

                try:
                    candles = executor.get_candles(asset, "FIFTEEN_MINUTE")
                    if not candles:
                        remaining_positions.append(trade)
                        continue

                    current_price = float(candles[-1]["close"])
                    exit_decision = profit_engine.evaluate(entry, current_price)

                    if exit_decision["action"] == "HOLD":
                        remaining_positions.append(trade)
                        continue

                    pnl_usd = (current_price - entry) * qty
                    governor.close_trade(asset, size_usd)

                    closed_messages.append(
                        f"{exit_decision['action']}: {asset} | Exit {current_price:.6f} | PnL {_fmt_money(pnl_usd)}"
                    )

                    if latest_status == "":
                        latest_status = closed_messages[-1]

                except Exception:
                    remaining_positions.append(trade)

            portfolio["positions"] = remaining_positions
            _save_portfolio(portfolio)

            positions = remaining_positions
            open_assets = {p["asset"] for p in positions}

            # 2. DISCOVER / SCORE NEW OPPORTUNITIES
            candidate_rows: List[Dict[str, Any]] = []
            candle_cache: Dict[str, List[Dict[str, Any]]] = {}

            initial_assets = universe[:seed_assets]

            for asset in initial_assets:
                try:
                    candles = executor.get_candles(asset, "FIFTEEN_MINUTE")
                except Exception:
                    continue

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

                candidate_rows.append(
                    {
                        "asset": asset,
                        "symbol": asset,
                        "asset_class": "CRYPTO",
                        "mid": mid,
                        "vwap": vwap,
                        "spread_bps": spread,
                        "signal": "BUY" if signal else "HOLD",
                        "reason": str(reason),
                        "regime": "MEAN_REVERSION",
                        "volume": _compute_candle_volume(candles),
                        "volatility": _compute_volatility(candles),
                    }
                )

            ai_results = ai.run(candidate_rows)

            selected_symbols = [
                str(item.get("symbol", "")).strip()
                for item in ai_results
                if str(item.get("signal", "HOLD")).upper() == "BUY"
            ]
            selected_symbols = [s for s in selected_symbols if s][:max_positions]

            ranked_symbols = selected_symbols or [
                str(item.get("symbol", "")).strip()
                for item in ai_results[:max_positions]
                if str(item.get("symbol", "")).strip()
            ]

            row_map = {row["asset"]: row for row in candidate_rows}
            rows = [row_map[s] for s in ranked_symbols if s in row_map]

            if not rows:
                rows = candidate_rows[:max_positions]

            allocations = _build_allocations(
                allocator=allocator,
                ai_results=ai_results,
                rows=rows,
                capital=capital,
                max_assets=max_positions,
            )

            # 3. EXECUTE NEW TRADES
            for row in rows:
                asset = row["asset"]
                mid = float(row["mid"])
                signal = str(row["signal"]).upper() == "BUY"

                if asset in open_assets:
                    continue
                if not signal:
                    continue

                candles = candle_cache.get(asset, [])
                decision = decision_engine.evaluate_trade(asset, candles)

                if not decision["execute_trade"]:
                    if latest_status == "":
                        latest_status = f"Intelligence block: {asset}"
                    continue

                alloc_size = 0.0
                for item in allocations:
                    if item.get("symbol") == asset:
                        alloc_size = float(item.get("capital", 0.0))
                        break

                if alloc_size <= 0:
                    if latest_status == "":
                        latest_status = f"No capital allocated to {asset}"
                    continue

                approved, msg = governor.approve_trade(asset, alloc_size)
                if not approved:
                    if latest_status == "":
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
                open_assets.add(asset)

                latest_status = f"TRADE ENTERED: {asset}"

            # 4. DASHBOARD OUTPUT
            _clear()

            print("====================================================================")
            print("             CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
            print("====================================================================")
            print(
                f"Cycle: {cycle_no} | Policy: {policy.policy_name} | Capital: {_fmt_money(capital)} | Refresh: {scan_interval}s"
            )
            print(f"Configured Base Assets: {', '.join(universe[:8])}")
            print(f"Timestamp (UTC): {_utc()}")

            print("\nOPEN POSITIONS")
            print("--------------------------------------------------------------------")

            if not positions:
                print("FLAT | No open spot positions")
            else:
                for p in positions:
                    print(
                        f"{p['asset']} | Entry {p['entry']} | Qty {p['qty']} | Size {_fmt_money(p['size_usd'])}"
                    )

            print("\nLIVE COINBASE EXECUTION WATCHLIST")
            print("--------------------------------------------------------------------")
            for r in rows[:3]:
                print(
                    f"{r['asset']:12} {r['mid']:10.4f} {r['vwap']:10.4f} {r['spread_bps']:10.2f} {r['signal']}"
                )

            print("\nAI OPPORTUNITY SCANNER")
            print("--------------------------------------------------------------------")
            print("Status: OK")
            for r in ai_results[:5]:
                print(f"{r.get('symbol')} score={r.get('opportunity_score', 0):.2f}")

            print("\nAI CAPITAL ALLOCATION PLAN")
            print("--------------------------------------------------------------------")
            for i, a in enumerate(allocations):
                print(f"{i+1}. {a['symbol']}  {_fmt_money(a['capital'])}")

            if closed_messages:
                print("\nCLOSED TRADES THIS CYCLE")
                print("--------------------------------------------------------------------")
                for msg in closed_messages:
                    print(msg)

            if latest_status:
                print("\nLATEST STATUS")
                print("--------------------------------------------------------------------")
                print(latest_status)

            print(f"\nRefreshing in {scan_interval} seconds...")
            time.sleep(scan_interval)

        except KeyboardInterrupt:
            print("CSS stopped")
            break

        except Exception as e:
            print("Runner error:", e)
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()