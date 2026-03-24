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


def format_money(value: float) -> str:
    return f"${value:,.4f}"


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


def get_net_pnl(trade: Dict[str, Any]) -> float:
    return safe_float(trade.get("realized_pnl_usd", trade.get("net_realized_pnl_usd", 0.0)), 0.0)


def get_gross_pnl(trade: Dict[str, Any]) -> float:
    net = get_net_pnl(trade)
    return safe_float(trade.get("gross_realized_pnl_usd"), net)


def get_cost(trade: Dict[str, Any]) -> float:
    return safe_float(trade.get("total_round_trip_cost_usd"), 0.0)


def pnl_bucket(trade: Dict[str, Any]) -> str:
    pnl = get_net_pnl(trade)
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "FLAT"


def classify_asset(trade: Dict[str, Any]) -> str:
    return str(trade.get("asset_class", "UNKNOWN")).upper()


def print_header(title: str) -> None:
    print("\n" + "=" * 58)
    print(title)
    print("=" * 58)


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

    total_net = sum(get_net_pnl(t) for t in closed_trades)
    total_gross = sum(get_gross_pnl(t) for t in closed_trades)
    total_cost = sum(get_cost(t) for t in closed_trades)

    wins = [t for t in closed_trades if get_net_pnl(t) > 0]
    losses = [t for t in closed_trades if get_net_pnl(t) < 0]
    flats = [t for t in closed_trades if get_net_pnl(t) == 0]

    win_rate = (len(wins) / closed_count * 100.0) if closed_count else 0.0
    loss_rate = (len(losses) / closed_count * 100.0) if closed_count else 0.0

    avg_hold_cycles = (
        sum(safe_int(t.get("cycles_held"), 0) for t in closed_trades) / closed_count
        if closed_count else 0.0
    )

    # Asset breakdown
    asset_stats: Dict[str, Dict[str, float]] = {}

    for t in closed_trades:
        asset = classify_asset(t)
        if asset not in asset_stats:
            asset_stats[asset] = {
                "count": 0,
                "net": 0.0,
                "gross": 0.0,
                "cost": 0.0,
            }

        asset_stats[asset]["count"] += 1
        asset_stats[asset]["net"] += get_net_pnl(t)
        asset_stats[asset]["gross"] += get_gross_pnl(t)
        asset_stats[asset]["cost"] += get_cost(t)

    best_trade = max(closed_trades, key=get_net_pnl) if closed_trades else None
    worst_trade = min(closed_trades, key=get_net_pnl) if closed_trades else None

    print_header("CAPITAL STRATA SYSTEMS - SESSION ANALYZER")

    print(f"Cycle No:              {summary.get('cycle_no', 'n/a')}")
    print(f"Estimated Equity:      {format_money(safe_float(summary.get('estimated_equity_usd'), 0.0))}")

    print_header("FINANCIAL PERFORMANCE")

    print(f"Gross Realized PnL:    {format_money(total_gross)}")
    print(f"Execution Cost Drag:   {format_money(total_cost)}")
    print(f"Net Realized PnL:      {format_money(total_net)}")

    if total_gross != 0:
        print(f"Cost Drag %:           {format_pct((total_cost / abs(total_gross)) * 100.0)}")

    print_header("TRADE OUTCOME SUMMARY")

    print(f"Closed Trades:         {closed_count}")
    print(f"Open Positions:        {open_count}")
    print(f"Win Rate:              {format_pct(win_rate)}")
    print(f"Loss Rate:             {format_pct(loss_rate)}")
    print(f"Flat Rate:             {format_pct((len(flats)/closed_count*100) if closed_count else 0.0)}")
    print(f"Average Hold Cycles:   {avg_hold_cycles:.2f}")

    print_header("ASSET CLASS PERFORMANCE")

    for asset, stats in asset_stats.items():
        print(
            f"{asset:10} trades={stats['count']} "
            f"gross={format_money(stats['gross'])} "
            f"cost={format_money(stats['cost'])} "
            f"net={format_money(stats['net'])}"
        )

    print_header("BEST / WORST TRADE")

    if best_trade:
        print(f"Best:  {best_trade.get('symbol')} {format_money(get_net_pnl(best_trade))}")
    if worst_trade:
        print(f"Worst: {worst_trade.get('symbol')} {format_money(get_net_pnl(worst_trade))}")

    print_header("RECENT CLOSED TRADES")

    for t in closed_trades[-10:]:
        print(
            f"{t.get('symbol'):12} "
            f"{pnl_bucket(t):5} "
            f"gross={format_money(get_gross_pnl(t))} "
            f"cost={format_money(get_cost(t))} "
            f"net={format_money(get_net_pnl(t))} "
            f"reason={t.get('exit_reason')} "
            f"held={safe_int(t.get('cycles_held'), 0)}"
        )


if __name__ == "__main__":
    analyze()