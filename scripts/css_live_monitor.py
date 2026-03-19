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


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def latest_close(closed_trades: List[Dict[str, Any]]) -> str:
    if not closed_trades:
        return "None"
    t = closed_trades[-1]
    symbol = str(t.get("symbol", "n/a"))
    pnl = safe_float(t.get("realized_pnl_usd"), 0.0)
    reason = str(t.get("exit_reason", "n/a"))
    return f"{symbol} | pnl={pnl:.4f} | reason={reason}"


def count_exit_reason(closed_trades: List[Dict[str, Any]], reason: str) -> int:
    target = reason.upper()
    return sum(1 for t in closed_trades if str(t.get("exit_reason", "")).upper() == target)


def total_realized_pnl(closed_trades: List[Dict[str, Any]]) -> float:
    return sum(safe_float(t.get("realized_pnl_usd"), 0.0) for t in closed_trades)


def open_symbols(open_positions: Dict[str, Any]) -> List[str]:
    if not isinstance(open_positions, dict):
        return []
    return sorted(str(k) for k in open_positions.keys())


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
        realized = total_realized_pnl(closed_trades)
        sl_count = count_exit_reason(closed_trades, "SL")
        tp_count = count_exit_reason(closed_trades, "TP")
        latest = latest_close(closed_trades)
        symbols = open_symbols(open_positions)

        clear()
        print("==============================================")
        print("      CAPITAL STRATA SYSTEMS LIVE MONITOR")
        print("==============================================\n")
        print(f"Cycle No:            {cycle}")
        print(f"Engine Mode:         {mode}")
        print(f"Estimated Equity:    ${eq:,.4f}")
        print(f"Open Positions:      {open_count}")
        print(f"Closed Trades:       {closed_count}")
        print(f"Total Realized PnL:  ${realized:,.4f}")
        print(f"TP Count:            {tp_count}")
        print(f"SL Count:            {sl_count}")
        print(f"Latest Close:        {latest}")

        print("\nOPEN SYMBOLS")
        print("----------------------------------------------")
        if symbols:
            for s in symbols:
                print(s)
        else:
            print("None")

        print(f"\nRefreshing in {REFRESH_SECONDS} seconds...")
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()