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

try:
    from backend.scanner.coinbase_universe import get_top_universe
except Exception:
    get_top_universe = None

try:
    from backend.execution.coinbase_executor import CoinbaseExecutor as _CoinbaseExecutor
    EXECUTOR_IMPORT_ERROR = ""
except Exception as exc:
    _CoinbaseExecutor = None
    EXECUTOR_IMPORT_ERROR = str(exc)


STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

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


def _default_position() -> Dict[str, Any]:
    return {
        "in_position": False,
        "asset": "",
        "entry": 0.0,
        "qty": 0.0,
        "size_usd": 0.0,
        "ts": "",
    }


def _load_position() -> Dict[str, Any]:
    if not POSITION_FILE.exists():
        return _default_position()

    try:
        payload = json.loads(POSITION_FILE.read_text())
        if not isinstance(payload, dict):
            return _default_position()
        return payload
    except Exception:
        return _default_position()


def _save_position(position: Dict[str, Any]) -> None:
    POSITION_FILE.write_text(json.dumps(position, indent=2))


class PublicCoinbaseMarketData:
    BASE_URL = "https://api.exchange.coinbase.com"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Capital-Strata-Systems/1.0",
                "Accept": "application/json",
            }
        )

    def get_candles(self, product_id: str, granularity_name: str) -> List[Dict[str, float]]:
        granularity_map = {
            "ONE_MINUTE": 60,
            "FIVE_MINUTE": 300,
            "FIFTEEN_MINUTE": 900,
            "ONE_HOUR": 3600,
            "SIX_HOUR": 21600,
            "ONE_DAY": 86400,
        }
        granularity = granularity_map.get(granularity_name, 900)

        url = f"{self.BASE_URL}/products/{product_id}/candles"
        response = self.session.get(
            url,
            params={"granularity": granularity},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        candles: List[Dict[str, float]] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                continue
            ts, low, high, open_, close, volume = row[:6]
            candles.append(
                {
                    "ts": float(ts),
                    "low": float(low),
                    "high": float(high),
                    "open": float(open_),
                    "close": float(close),
                    "volume": float(volume),
                }
            )

        candles.sort(key=lambda x: x["ts"])
        return candles


def _build_market_adapter() -> Tuple[Any, str, bool]:
    if _CoinbaseExecutor is not None:
        try:
            adapter = _CoinbaseExecutor()
            return adapter, "CoinbaseExecutor(paper_mode=True)", True
        except Exception as exc:
            return (
                PublicCoinbaseMarketData(),
                f"PublicCoinbaseFallback(executor init failed: {exc})",
                False,
            )

    reason = EXECUTOR_IMPORT_ERROR or "unknown import error"
    return (
        PublicCoinbaseMarketData(),
        f"PublicCoinbaseFallback(import failed: {reason})",
        False,
    )


def _base_assets_from_universe() -> List[str]:
    if get_top_universe is not None:
        try:
            universe = get_top_universe(200)
            if universe:
                return universe
        except Exception:
            pass

    return [x.strip() for x in _env("CSS_PRODUCTS", "BTC-USD,ETH-USD").split(",") if x.strip()]


def _select_execution_assets(
    ai_results: List[Dict[str, Any]],
    fallback_assets: List[str],
    max_assets: int,
) -> Tuple[List[str], str]:
    selected: List[str] = []

    for item in ai_results:
        asset_class = str(item.get("asset_class", "")).upper()
        signal = str(item.get("signal", "")).upper()
        symbol = str(item.get("symbol", "")).strip()

        if asset_class != "CRYPTO":
            continue
        if signal != "BUY":
            continue
        if not symbol.endswith("-USD"):
            continue

        selected.append(symbol)
        if len(selected) >= max_assets:
            break

    deduped: List[str] = []
    seen = set()
    for symbol in selected:
        if symbol not in seen:
            deduped.append(symbol)
            seen.add(symbol)

    if deduped:
        return deduped, "AI_DYNAMIC"

    return fallback_assets[:max_assets], "UNIVERSE_FALLBACK"


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_num(value: float, decimals: int = 4) -> str:
    return f"{value:.{decimals}f}"


def _print_header(
    policy_name: str,
    starting_capital: float,
    trade_size: float,
    scan_interval: int,
    configured_assets: List[str],
    active_assets: List[str],
    watchlist_source: str,
    adapter_label: str,
    trading_enabled: bool,
) -> None:
    print("================================================================================")
    print("                         CAPITAL STRATA SYSTEMS LIVE DASHBOARD")
    print("================================================================================")
    print(
        f"Policy: {policy_name} | Capital: {_fmt_money(starting_capital)} | "
        f"Trade Size: {_fmt_money(trade_size)} | Refresh: {scan_interval}s"
    )
    if len(configured_assets) > 8:
        preview = ", ".join(configured_assets[:8]) + f" ... ({len(configured_assets)} assets)"
    else:
        preview = ", ".join(configured_assets)

    print(f"Configured Base Assets: {preview}")
    print(f"Active Execution Watchlist: {', '.join(active_assets)}")
    print(f"Watchlist Source: {watchlist_source}")
    print(f"Market Adapter: {adapter_label}")
    print(f"Trading Enabled: {'YES' if trading_enabled else 'NO - DASHBOARD MODE'}")
    print(f"Timestamp (UTC): {_utc()}")
    print("================================================================================\n")


def _print_position(position: Dict[str, Any]) -> None:
    print("POSITION STATUS")
    print("--------------------------------------------------------------------------------")
    if position.get("in_position", False):
        print(
            f"OPEN | Asset: {position.get('asset', '')} | "
            f"Entry: {_fmt_num(float(position.get('entry', 0.0)), 6)} | "
            f"Qty: {_fmt_num(float(position.get('qty', 0.0)), 6)} | "
            f"Size: {_fmt_money(float(position.get('size_usd', 0.0)))}"
        )
    else:
        print("FLAT | No open spot position")
    print()


def _print_market_scan(rows: List[Dict[str, Any]]) -> None:
    print("LIVE COINBASE EXECUTION WATCHLIST")
    print("--------------------------------------------------------------------------------")
    print(
        f"{'Asset':12} {'Mid':>12} {'VWAP':>12} {'Spread(bps)':>12} "
        f"{'Signal':>8} {'Reason':>16}"
    )
    print("-" * 82)

    if not rows:
        print("No scan rows available.\n")
        return

    for row in rows:
        print(
            f"{row['asset']:<12} "
            f"{row['mid']:>12.6f} "
            f"{row['vwap']:>12.6f} "
            f"{row['spread_bps']:>12.2f} "
            f"{row['signal_text']:>8} "
            f"{row['reason_short']:>16}"
        )
    print()


def _print_ai_panel(items: List[Dict[str, Any]]) -> None:
    print("AI OPPORTUNITY SCANNER")
    print("--------------------------------------------------------------------------------")
    print(
        f"{'Symbol':12} {'Class':8} {'Signal':8} {'Regime':16} "
        f"{'AI Score':>8} {'Band':10} {'Priority':14}"
    )
    print("-" * 96)

    if not items:
        print("No AI opportunities available.\n")
        return

    for item in items[:8]:
        print(
            f"{item['symbol']:<12} "
            f"{item['asset_class']:<8} "
            f"{item['signal']:<8} "
            f"{item['regime']:<16} "
            f"{item['opportunity_score']:>8.2f} "
            f"{item['confidence_band']:<10} "
            f"{item['action_priority']:<14}"
        )

    print("\nTop AI explanations:")
    for item in items[:3]:
        print(f"- {item['explanation']}")
    print()


def _print_capital_plan(allocations: List[Dict[str, Any]], total_capital: float) -> None:
    print("AI CAPITAL ALLOCATION PLAN")
    print("--------------------------------------------------------------------------------")
    print(f"{'Rank':4} {'Symbol':12} {'AI Score':>10} {'Capital':>12}")
    print("-" * 44)

    if not allocations:
        print("No capital allocations available.\n")
        return

    allocated_total = 0.0
    for idx, item in enumerate(allocations, start=1):
        allocated_total += float(item["capital"])
        print(
            f"{idx:<4} "
            f"{item['symbol']:<12} "
            f"{item['ai_score']:>10.2f} "
            f"{_fmt_money(float(item['capital'])):>12}"
        )

    print("-" * 44)
    print(
        f"Allocated: {_fmt_money(allocated_total)} | "
        f"Portfolio Capital Basis: {_fmt_money(total_capital)}"
    )
    print()


def main() -> None:
    scan_interval = _env_int("CSS_SCAN_INTERVAL_SECONDS", 45)
    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200.0)
    trade_size = _env_float("CSS_TRADE_SIZE_USD", 20.0)
    max_dynamic_assets = _env_int("CSS_DYNAMIC_TOP_N", 5)

    configured_assets = _base_assets_from_universe()

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    policy = choose_session_policy(starting_capital)
    governor = PortfolioRiskGovernor(policy)

    adapter, adapter_label, trading_enabled = _build_market_adapter()
    ai_scorer = AIOpportunityScorer()
    allocator = CapitalAllocator(
        total_capital=starting_capital,
        max_positions=max_dynamic_assets,
    )

    last_ai_results: List[Dict[str, Any]] = []
    last_allocations: List[Dict[str, Any]] = []
    last_status = ""

    while True:
        try:
            position = _load_position()
            scan_rows: List[Dict[str, Any]] = []

            try:
                last_ai_results = ai_scorer.run()
            except Exception as ai_exc:
                last_status = f"AI scorer error: {ai_exc}"
                last_ai_results = []

            active_assets, watchlist_source = _select_execution_assets(
                ai_results=last_ai_results,
                fallback_assets=configured_assets,
                max_assets=max_dynamic_assets,
            )

            for asset in active_assets:
                candles = adapter.get_candles(asset, "FIFTEEN_MINUTE")

                if len(candles) < 20:
                    scan_rows.append(
                        {
                            "asset": asset,
                            "mid": 0.0,
                            "vwap": 0.0,
                            "spread_bps": 0.0,
                            "signal_text": "N/A",
                            "reason_short": "few_candles",
                        }
                    )
                    continue

                vwap = compute_vwap_from_candles(candles, 20)
                mid = float(candles[-1]["close"])
                spread_bps = ((mid - vwap) / vwap) * 10000.0

                signal, reason = should_buy_mean_reversion(
                    mid,
                    vwap,
                    spread_bps,
                    vwap_cfg,
                )

                scan_rows.append(
                    {
                        "asset": asset,
                        "mid": mid,
                        "vwap": vwap,
                        "spread_bps": spread_bps,
                        "signal_text": "BUY" if signal else "HOLD",
                        "reason_short": str(reason)[:16],
                    }
                )

                if not trading_enabled:
                    continue

                if position.get("in_position", False):
                    continue

                if not signal:
                    continue

                approved, msg = governor.approve_trade(asset, trade_size)
                if not approved:
                    last_status = f"Risk block: {msg}"
                    continue

                qty = trade_size / mid
                governor.register_trade(asset, trade_size)

                position = {
                    "in_position": True,
                    "asset": asset,
                    "entry": mid,
                    "qty": qty,
                    "size_usd": trade_size,
                    "ts": _utc(),
                }
                _save_position(position)
                last_status = f"TRADE ENTERED: {asset} @ {mid:.6f}"

            try:
                last_allocations = allocator.allocate(
                    ai_results=last_ai_results,
                    market_rows=scan_rows,
                )
            except Exception as alloc_exc:
                last_status = f"Allocator error: {alloc_exc}"
                last_allocations = []

            _clear()
            _print_header(
                policy_name=policy.policy_name,
                starting_capital=starting_capital,
                trade_size=trade_size,
                scan_interval=scan_interval,
                configured_assets=configured_assets,
                active_assets=active_assets,
                watchlist_source=watchlist_source,
                adapter_label=adapter_label,
                trading_enabled=trading_enabled,
            )
            _print_position(position)
            _print_market_scan(scan_rows)
            _print_ai_panel(last_ai_results)
            _print_capital_plan(last_allocations, starting_capital)

            if last_status:
                print("LATEST STATUS")
                print("--------------------------------------------------------------------------------")
                print(last_status)
                print()

            print(f"Refreshing in {scan_interval} seconds...  Press Ctrl+C to stop.")
            time.sleep(scan_interval)

        except KeyboardInterrupt:
            print("\nCSS stopped")
            break

        except Exception as exc:
            _clear()
            print("CSS live dashboard error:", exc)
            print(f"Retrying in {scan_interval} seconds...")
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()