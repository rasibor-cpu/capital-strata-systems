from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATE_DIR = PROJECT_ROOT / "backend" / "state"
AUDIT_DIR = PROJECT_ROOT / "audit_logs"

SPOT_FILE = STATE_DIR / "spot_position.json"
ACCOUNT_FILE = STATE_DIR / "account_state.json"
TRADES_FILE = AUDIT_DIR / "trades.jsonl"

REFRESH = 30
LINE = "------------------------------"


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def compute() -> Dict[str, Any]:
    spot = read_json(SPOT_FILE)
    acct = read_json(ACCOUNT_FILE)
    trades = read_jsonl(TRADES_FILE)

    positions = spot.get("positions", [])
    if not isinstance(positions, list):
        positions = []

    cash = safe_float(
        acct.get("cash")
        or acct.get("cash_usd")
        or acct.get("available_cash")
        or 0
    )

    market = 0.0
    unreal = 0.0

    normalized_positions: List[Dict[str, Any]] = []
    for p in positions:
        asset = str(p.get("asset") or p.get("symbol") or "UNKNOWN")
        value = safe_float(p.get("market_value"))
        if value == 0.0:
            qty = safe_float(p.get("quantity") or p.get("qty"))
            px = safe_float(p.get("current_price") or p.get("price"))
            value = qty * px

        upnl = safe_float(p.get("unrealized_pnl"))
        market += value
        unreal += upnl

        normalized_positions.append(
            {
                "asset": asset,
                "market_value": value,
                "unrealized_pnl": upnl,
            }
        )

    normalized_positions.sort(key=lambda x: abs(x["market_value"]), reverse=True)

    realized = 0.0
    fees = 0.0

    normalized_trades: List[Dict[str, Any]] = []
    for t in trades:
        asset = str(t.get("asset") or t.get("symbol") or "UNKNOWN")
        gross = safe_float(t.get("realized_pnl") or t.get("pnl"))
        fee = safe_float(t.get("fee") or t.get("fees"))
        net = gross - fee

        realized += gross
        fees += fee

        normalized_trades.append(
            {
                "asset": asset,
                "net_pnl": net,
            }
        )

    realized_net = realized - fees
    equity = cash + market
    pnl = realized_net + unreal

    return {
        "cash": cash,
        "market": market,
        "equity": equity,
        "realized": realized_net,
        "unreal": unreal,
        "pnl": pnl,
        "positions": normalized_positions,
        "trades": normalized_trades,
    }


def render_card(title: str) -> None:
    print(LINE)
    print(title)
    print(LINE)


def render() -> None:
    data = compute()

    print("CSS MOBILE DASHBOARD")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    render_card("BALANCE")
    print(f"Cash     {money(data['cash'])}")
    print(f"Pos Val  {money(data['market'])}")
    print(f"Equity   {money(data['equity'])}")
    print(f"Net P&L  {money(data['pnl'])}")
    print(f"R / U    {money(data['realized'])} / {money(data['unreal'])}")
    print()

    render_card("TOP POSITIONS")
    if not data["positions"]:
        print("No open positions")
    else:
        for p in data["positions"][:4]:
            print(f"{p['asset']:<8} {money(p['market_value']):>10}")
            print(f"UPnL     {money(p['unrealized_pnl'])}")
    print()

    render_card("LAST TRADES")
    if not data["trades"]:
        print("No trades")
    else:
        for t in data["trades"][-3:]:
            print(f"{t['asset']:<8} {money(t['net_pnl'])}")
    print()


def main() -> None:
    while True:
        clear()
        render()
        time.sleep(REFRESH)


if __name__ == "__main__":
    main()