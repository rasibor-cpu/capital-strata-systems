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

from backend.intelligence.ai_opportunity_scorer import AIOpportunityScorer
from backend.risk.portfolio_risk_governor import PortfolioRiskGovernor
from backend.risk.session_policy_loader import choose_session_policy
from backend.strategies.vwap_mean_reversion import (
    VWAPConfig,
    compute_vwap_from_candles,
    should_buy_mean_reversion,
)

try:
    from backend.execution.coinbase_executor import CoinbaseExecutor
except Exception:
    CoinbaseExecutor = None


STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

STATE_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

POSITION_FILE = STATE_DIR / "spot_position.json"


# ---------------- ENV HELPERS ----------------

def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return default if v is None else str(v)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


# ---------------- POSITION STATE ----------------

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


# ---------------- DASHBOARD RENDER ----------------

def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_num(value: float, decimals: int = 4) -> str:
    return f"{value:.{decimals}f}"


def _print_header(
    policy_name: str,
    starting_capital: float,
    trade_size: float,
    scan_interval: int,
    assets: List[str],
) -> None:
    print("==============================================================")
    print("                 CAPITAL STRATA SYSTEMS (CSS)")
    print("==============================================================")
    print(
        f"Policy: {policy_name} | Capital: {_fmt_money(starting_capital)} | "
        f"Trade Size: {_fmt_money(trade_size)} | Refresh: {scan_interval}s"
    )
    print(f"Configured Coinbase Assets: {', '.join(assets)}")
    print(f"Timestamp (UTC): {_utc()}")
    print("==============================================================\n")


def _print_position(position: Dict[str, Any]) -> None:
    print("POSITION STATUS")
    print("--------------------------------------------------------------")
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
    print("--------------------------------------------------------------")
    print(
        f"{'Asset':12} {'Mid':>12} {'VWAP':>12} {'Spread(bps)':>12} "
        f"{'Signal':>8} {'Reason':>14}"
    )
    print("-" * 74)

    if not rows:
        print("No scan rows available.")
        print()
        return

    for row in rows:
        print(
            f"{row['asset']:<12} "
            f"{row['mid']:>12.6f} "
            f"{row['vwap']:>12.6f} "
            f"{row['spread_bps']:>12.2f} "
            f"{row['signal_text']:>8} "
            f"{row['reason_short']:>14}"
        )
    print()


def _print_ai_panel(items: List[Dict[str, Any]]) -> None:
    print("AI OPPORTUNITY SCANNER")
    print("--------------------------------------------------------------")
    print(
        f"{'Symbol':12} {'Class':8} {'Signal':8} {'Regime':16} "
        f"{'AI Score':>8} {'Band':10} {'Priority':14}"
    )
    print("-" * 92)

    if not items:
        print("No AI opportunities available.")
        print()
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


# ---------------- MAIN ----------------

def main() -> None:
    scan_interval = int(_env_float("CSS_SCAN_INTERVAL_SECONDS", 20))
    starting_capital = _env_float("CSS_STARTING_CAPITAL_USD", 200.0)
    trade_size = _env_float("CSS_TRADE_SIZE_USD", 20.0)

    assets = [x.strip() for x in _env("CSS_PRODUCTS", "BTC-USD,ETH-USD").split(",") if x.strip()]

    vwap_cfg = VWAPConfig(
        window=20,
        epsilon_bps=12,
        take_profit_bps=35,
        stop_loss_bps=45,
    )

    policy = choose_session_policy(starting_capital)
    governor = PortfolioRiskGovernor(policy)

    if CoinbaseExecutor is None:
        print("Coinbase executor is unavailable. CSS cannot start.")
        return

    executor = CoinbaseExecutor(paper_mode=True)
    ai_scorer = AIOpportunityScorer()

    last_ai_results: List[Dict[str, Any]] = []
    last_error = ""

    while True:
        try:
            position = _load_position()
            scan_rows: List[Dict[str, Any]] = []

            for asset in assets:
                candles = executor.get_candles(asset, "FIFTEEN_MINUTE")
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
                        "reason_short": str(reason)[:14],
                    }
                )

                # Existing execution logic preserved
                if position.get("in_position", False):
                    continue

                if not signal:
                    continue

                approved, msg = governor.approve_trade(asset, trade_size)
                if not approved:
                    last_error = f"Risk block: {msg}"
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
                last_error = f"TRADE ENTERED: {asset} @ {mid:.6f}"

            try:
                last_ai_results = ai_scorer.run()
            except Exception as ai_exc:
                last_error = f"AI scorer error: {ai_exc}"

            _clear()
            _print_header(
                policy_name=policy.policy_name,
                starting_capital=starting_capital,
                trade_size=trade_size,
                scan_interval=scan_interval,
                assets=assets,
            )
            _print_position(position)
            _print_market_scan(scan_rows)
            _print_ai_panel(last_ai_results)

            if last_error:
                print("LATEST STATUS")
                print("--------------------------------------------------------------")
                print(last_error)
                print()

            print(f"Refreshing in {scan_interval} seconds...  Press Ctrl+C to stop.")
            time.sleep(scan_interval)

        except KeyboardInterrupt:
            print("\nCSS stopped")
            break

        except Exception as exc:
            _clear()
            print("CSS live runner error:", exc)
            print(f"Retrying in {scan_interval} seconds...")
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()