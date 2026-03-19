from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"

SUMMARY_FILE = ARTIFACT_DIR / "css_extended_paper_test_summary.json"
POSITIONS_FILE = ARTIFACT_DIR / "css_open_positions.json"
CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"


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


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def pnl_bucket(trade: Dict[str, Any]) -> str:
    pnl = safe_float(trade.get("realized_pnl_usd"), 0.0)
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "FLAT"


def format_money(value: float) -> str:
    return f"${value:,.4f}"


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def print_header(title: str) -> None:
    print("\n" + "=" * 54)
    print(f"{title}")
    print("=" * 54)


def analyze() -> None:
    summary = load_json_file(SUMMARY_FILE, {})
    open_positions = load_json_file(POSITIONS_FILE, {})
    closed_trades = load_json_file(CLOSED_TRADES_FILE, [])

    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(open_positions, dict):
        open_positions = {}
    if not isinstance(closed_trades, list):
        closed_trades = []

    closed_count = len(closed_trades)
    open_count = len(open_positions)

    total_realized_pnl = sum(
        safe_float(t.get("realized_pnl_usd"), 0.0) for t in closed_trades
    )

    wins = [t for t in closed_trades if safe_float(t.get("realized_pnl_usd"), 0.0) > 0]
    losses = [t for t in closed_trades if safe_float(t.get("realized_pnl_usd"), 0.0) < 0]
    flats = [t for t in closed_trades if safe_float(t.get("realized_pnl_usd"), 0.0) == 0]

    win_rate = (len(wins) / closed_count * 100.0) if closed_count else 0.0
    loss_rate = (len(losses) / closed_count * 100.0) if closed_count else 0.0

    sl_count = sum(
        1 for t in closed_trades
        if str(t.get("exit_reason", "")).upper() == "SL"
    )
    tp_count = sum(
        1 for t in closed_trades
        if str(t.get("exit_reason", "")).upper() == "TP"
    )
    time_count = sum(
        1 for t in closed_trades
        if str(t.get("exit_reason", "")).upper() not in {"SL", "TP"}
    )

    avg_hold_cycles = (
        sum(safe_int(t.get("cycles_held"), 0) for t in closed_trades) / closed_count
        if closed_count
        else 0.0
    )

    open_notional = 0.0
    for symbol, position in open_positions.items():
        if not isinstance(position, dict):
            continue
        qty = safe_float(position.get("quantity"), 0.0)
        entry = safe_float(position.get("entry_price"), 0.0)
        open_notional += qty * entry

    best_trade = None
    worst_trade = None
    if closed_trades:
        best_trade = max(closed_trades, key=lambda t: safe_float(t.get("realized_pnl_usd"), 0.0))
        worst_trade = min(closed_trades, key=lambda t: safe_float(t.get("realized_pnl_usd"), 0.0))

    print_header("CAPITAL STRATA SYSTEMS - SESSION ANALYZER")

    print(f"Timestamp UTC:         {summary.get('timestamp_utc', 'n/a')}")
    print(f"Cycle No:              {summary.get('cycle_no', 'n/a')}")
    print(f"Engine Mode:           {summary.get('engine_mode', 'n/a')}")
    print(f"Estimated Equity:      {format_money(safe_float(summary.get('estimated_equity_usd'), 0.0))}")
    print(f"Starting Capital:      {format_money(safe_float(summary.get('starting_capital_usd'), 0.0))}")
    print(f"Cycle Realized PnL:    {format_money(safe_float(summary.get('cycle_realized_pnl_usd'), 0.0))}")

    print_header("TRADE OUTCOME SUMMARY")

    print(f"Closed Trades:         {closed_count}")
    print(f"Open Positions:        {open_count}")
    print(f"Total Realized PnL:    {format_money(total_realized_pnl)}")
    print(f"Win Rate:              {format_pct(win_rate)}")
    print(f"Loss Rate:             {format_pct(loss_rate)}")
    print(f"Flat Rate:             {format_pct((len(flats) / closed_count * 100.0) if closed_count else 0.0)}")
    print(f"Average Hold Cycles:   {avg_hold_cycles:.2f}")
    print(f"Open Notional @ Entry: {format_money(open_notional)}")

    print_header("EXIT REASON BREAKDOWN")

    print(f"TP Count:              {tp_count}")
    print(f"SL Count:              {sl_count}")
    print(f"Other Exit Count:      {time_count}")

    print_header("BEST / WORST CLOSED TRADE")

    if best_trade:
        print(
            f"Best Trade:            {best_trade.get('symbol', 'n/a')} | "
            f"{format_money(safe_float(best_trade.get('realized_pnl_usd'), 0.0))} | "
            f"reason={best_trade.get('exit_reason', 'n/a')} | "
            f"held={safe_int(best_trade.get('cycles_held'), 0)}"
        )
    else:
        print("Best Trade:            n/a")

    if worst_trade:
        print(
            f"Worst Trade:           {worst_trade.get('symbol', 'n/a')} | "
            f"{format_money(safe_float(worst_trade.get('realized_pnl_usd'), 0.0))} | "
            f"reason={worst_trade.get('exit_reason', 'n/a')} | "
            f"held={safe_int(worst_trade.get('cycles_held'), 0)}"
        )
    else:
        print("Worst Trade:           n/a")

    print_header("OPEN POSITIONS")

    if not open_positions:
        print("No open positions.")
    else:
        for symbol, position in open_positions.items():
            if not isinstance(position, dict):
                continue
            qty = safe_float(position.get("quantity"), 0.0)
            entry = safe_float(position.get("entry_price"), 0.0)
            cycles_held = safe_int(position.get("cycles_held"), 0)
            opened_at = position.get("opened_at", "n/a")
            print(
                f"{symbol:12} qty={qty:.8f} "
                f"entry={entry:.8f} "
                f"held={cycles_held} "
                f"opened_at={opened_at}"
            )

    print_header("RECENT CLOSED TRADES")

    if not closed_trades:
        print("No closed trades yet.")
    else:
        recent = closed_trades[-10:]
        for trade in recent:
            symbol = trade.get("symbol", "n/a")
            pnl = safe_float(trade.get("realized_pnl_usd"), 0.0)
            exit_reason = trade.get("exit_reason", "n/a")
            held = safe_int(trade.get("cycles_held"), 0)
            bucket = pnl_bucket(trade)
            print(
                f"{symbol:12} {bucket:5} "
                f"pnl={format_money(pnl):>12} "
                f"reason={exit_reason:>4} "
                f"held={held}"
            )


if __name__ == "__main__":
    analyze()