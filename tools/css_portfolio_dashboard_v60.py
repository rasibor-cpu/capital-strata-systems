import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATE_FILE = PROJECT_ROOT / "backend" / "state" / "spot_position.json"
TRADES_FILE = PROJECT_ROOT / "audit_logs" / "trades.jsonl"

STARTING_CAPITAL = 200.00
REFRESH_SECONDS = 5


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_position() -> Optional[Dict[str, Any]]:
    if not STATE_FILE.exists():
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_trades() -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []

    if not TRADES_FILE.exists():
        return trades

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        trades.append(item)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []

    return trades


def compute_realized(trades: List[Dict[str, Any]]) -> float:
    pnl = 0.0
    for t in trades:
        pnl += _safe_float(t.get("realized_pnl", 0.0))
    return pnl


def get_position_asset(position: Optional[Dict[str, Any]]) -> str:
    if not position:
        return "-"
    return str(
        position.get("asset")
        or position.get("symbol")
        or position.get("product_id")
        or position.get("pair")
        or "-"
    )


def get_position_qty(position: Optional[Dict[str, Any]]) -> float:
    if not position:
        return 0.0
    return _safe_float(
        position.get("size",
        position.get("qty",
        position.get("quantity",
        position.get("base_size", 0.0))))
    )


def get_entry_price(position: Optional[Dict[str, Any]]) -> float:
    if not position:
        return 0.0
    return _safe_float(
        position.get("entry_price",
        position.get("entry",
        position.get("avg_entry_price",
        position.get("average_entry_price",
        position.get("avg_price",
        position.get("price", 0.0))))))
    )


def get_current_price(position: Optional[Dict[str, Any]]) -> float:
    if not position:
        return 0.0
    return _safe_float(
        position.get("current_price",
        position.get("mark_price",
        position.get("market_price",
        position.get("last_price",
        position.get("price", 0.0)))))
    )


def has_open_position(position: Optional[Dict[str, Any]]) -> bool:
    if not position:
        return False

    qty = get_position_qty(position)
    status = str(position.get("status", "")).strip().lower()

    if qty > 0:
        return True

    if status in {"open", "active", "filled", "live"}:
        return True

    return False


def compute_unrealized(position: Optional[Dict[str, Any]]) -> float:
    if not has_open_position(position):
        return 0.0

    entry = get_entry_price(position)
    current = get_current_price(position)
    qty = get_position_qty(position)

    if qty <= 0 or entry <= 0 or current <= 0:
        return 0.0

    return (current - entry) * qty


def compute_market_value(position: Optional[Dict[str, Any]]) -> float:
    if not has_open_position(position):
        return 0.0

    current = get_current_price(position)
    qty = get_position_qty(position)

    if current <= 0 or qty <= 0:
        return 0.0

    return current * qty


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def render_dashboard() -> None:
    last_refresh_label = ""

    while True:
        pos = load_position()
        trades = load_trades()

        realized = compute_realized(trades)
        unrealized = compute_unrealized(pos)
        market_value = compute_market_value(pos)

        cash_balance = STARTING_CAPITAL + realized
        total_equity = cash_balance + unrealized

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_refresh_label = timestamp

        clear_screen()
        print()
        print("====================================================")
        print(" CAPITAL STRATA SYSTEMS — LIVE PORTFOLIO DASHBOARD ")
        print("====================================================")
        print(f" Local Time        : {timestamp}")
        print(f" Last Refresh      : {last_refresh_label}")
        print()

        print("---------------- ACCOUNT SUMMARY -------------------")
        print(f" Starting Capital  : ${STARTING_CAPITAL:,.2f}")
        print(f" Cash Balance      : ${cash_balance:,.2f}")
        print(f" Realized PnL      : ${realized:,.2f}")
        print(f" Unrealized PnL    : ${unrealized:,.2f}")
        print(f" Total Equity      : ${total_equity:,.2f}")
        print()

        print("---------------- OPEN POSITION ---------------------")
        if has_open_position(pos):
            asset = get_position_asset(pos)
            qty = get_position_qty(pos)
            entry = get_entry_price(pos)
            current = get_current_price(pos)

            print(f" Asset             : {asset}")
            print(f" Quantity          : {qty:,.8f}")
            print(f" Entry Price       : ${entry:,.8f}")
            print(f" Current Price     : ${current:,.8f}")
            print(f" Market Value      : ${market_value:,.2f}")
            print(f" Position PnL      : ${unrealized:,.2f}")
        else:
            print(" No open position")
        print()

        print("---------------- TRADE LOG -------------------------")
        print(f" Total Trades      : {len(trades)}")
        print()
        print(f" Auto Refresh      : every {REFRESH_SECONDS} seconds")
        print("====================================================")

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    render_dashboard()