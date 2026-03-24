from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"

REFRESH_SECONDS = 5


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def format_money(v: float) -> str:
    return f"${v:,.4f}"


def classify_symbol(symbol: str) -> str:
    s = str(symbol).upper().strip()

    if "PERP" in s or "FUT" in s:
        return "FUTURES"

    if "_" in s:
        parts = s.split("_")
        if len(parts) == 2 and len(parts[0]) == 3 and len(parts[1]) == 3:
            return "FX"

    if len(s) == 6 and s.isalpha():
        return "FX"

    if "-" in s or "/" in s:
        return "CRYPTO"

    return "OTHER"


def latest_close(closed_trades: List[Dict[str, Any]]) -> str:
    if not closed_trades:
        return "None"

    t = closed_trades[-1]
    symbol = str(t.get("symbol", "n/a"))
    gross = safe_float(t.get("gross_realized_pnl_usd"), safe_float(t.get("realized_pnl_usd"), 0.0))
    net = safe_float(t.get("realized_pnl_usd", t.get("net_realized_pnl_usd", 0.0)), 0.0)
    cost = safe_float(t.get("total_round_trip_cost_usd"), 0.0)
    reason = str(t.get("exit_reason", "n/a"))
    return f"{symbol} | gross={gross:.4f} | cost={cost:.4f} | net={net:.4f} | reason={reason}"


def count_exit_reason(closed_trades: List[Dict[str, Any]], reason: str) -> int:
    target = reason.upper()
    return sum(1 for t in closed_trades if str(t.get("exit_reason", "")).upper() == target)


def total_net_realized_pnl(closed_trades: List[Dict[str, Any]]) -> float:
    return sum(
        safe_float(t.get("realized_pnl_usd", t.get("net_realized_pnl_usd", 0.0)), 0.0)
        for t in closed_trades
    )


def total_gross_realized_pnl(closed_trades: List[Dict[str, Any]]) -> float:
    total = 0.0
    for t in closed_trades:
        net = safe_float(t.get("realized_pnl_usd", t.get("net_realized_pnl_usd", 0.0)), 0.0)
        gross = safe_float(t.get("gross_realized_pnl_usd"), net)
        total += gross
    return total


def total_execution_cost(closed_trades: List[Dict[str, Any]]) -> float:
    return sum(safe_float(t.get("total_round_trip_cost_usd"), 0.0) for t in closed_trades)


def open_symbols(open_positions: Dict[str, Any]) -> List[str]:
    if not isinstance(open_positions, dict):
        return []
    return sorted(str(k) for k in open_positions.keys())


def open_position_asset_mix(open_positions: Dict[str, Any]) -> Dict[str, int]:
    mix = {"FX": 0, "CRYPTO": 0, "FUTURES": 0, "OTHER": 0}

    if not isinstance(open_positions, dict):
        return mix

    for symbol, pos in open_positions.items():
        asset_class = str(pos.get("asset_class", "")).upper().strip()
        if asset_class not in mix:
            asset_class = classify_symbol(symbol)
        mix[asset_class] = mix.get(asset_class, 0) + 1

    return mix


def main() -> None:
    while True:
        summary = load_json(SUMMARY_FILE, {})
        open_positions = load_json(POSITIONS_FILE, {})
        closed_trades = load_json(CLOSED_TRADES_FILE, [])

        if not isinstance(summary, dict):
            summary = {}
        if not isinstance(open_positions, dict):
            open_positions = {}
        if not isinstance(closed_trades, list):
            closed_trades = []

        eq = safe_float(summary.get("estimated_equity_usd"), 0.0)
        cycle = summary.get("cycle_no", "n/a")
        mode = summary.get("engine_mode", "n/a")
        open_count = len(open_positions)
        closed_count = len(closed_trades)

        net_realized = total_net_realized_pnl(closed_trades)
        gross_realized = total_gross_realized_pnl(closed_trades)
        cost_drag = total_execution_cost(closed_trades)

        sl_count = count_exit_reason(closed_trades, "SL")
        tp_count = count_exit_reason(closed_trades, "TP")
        early_tp_count = count_exit_reason(closed_trades, "EARLY_TP")
        decay_count = count_exit_reason(closed_trades, "SIGNAL_DECAY")
        time_count = count_exit_reason(closed_trades, "TIME")

        latest = latest_close(closed_trades)
        symbols = open_symbols(open_positions)
        asset_mix = open_position_asset_mix(open_positions)

        clear()
        print("============================================================")
        print("            CAPITAL STRATA SYSTEMS LIVE MONITOR")
        print("============================================================\n")
        print(f"Cycle No:               {cycle}")
        print(f"Engine Mode:            {mode}")
        print(f"Estimated Equity:       {format_money(eq)}")
        print(f"Open Positions:         {open_count}")
        print(f"Closed Trades:          {closed_count}")

        print("\n---------------- FINANCIAL SUMMARY ----------------\n")
        print(f"Gross Realized PnL:     {format_money(gross_realized)}")
        print(f"Execution Cost Drag:    {format_money(cost_drag)}")
        print(f"Net Realized PnL:       {format_money(net_realized)}")

        print("\n---------------- EXIT REASONS ----------------\n")
        print(f"TP Count:               {tp_count}")
        print(f"SL Count:               {sl_count}")
        print(f"EARLY_TP Count:         {early_tp_count}")
        print(f"SIGNAL_DECAY Count:     {decay_count}")
        print(f"TIME Count:             {time_count}")

        print("\n---------------- OPEN POSITION MIX ----------------\n")
        print(f"FX:                     {asset_mix.get('FX', 0)}")
        print(f"CRYPTO:                 {asset_mix.get('CRYPTO', 0)}")
        print(f"FUTURES:                {asset_mix.get('FUTURES', 0)}")
        print(f"OTHER:                  {asset_mix.get('OTHER', 0)}")

        print("\n---------------- LATEST CLOSE ----------------\n")
        print(latest)

        print("\n---------------- OPEN SYMBOLS ----------------\n")
        if symbols:
            for s in symbols:
                print(s)
        else:
            print("None")

        print(f"\nRefreshing in {REFRESH_SECONDS} seconds...")
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()