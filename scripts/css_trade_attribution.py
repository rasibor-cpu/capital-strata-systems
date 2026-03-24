from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"

CLOSED_TRADES_FILE = ARTIFACT_DIR / "css_closed_trades.json"


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def load_closed_trades() -> List[Dict[str, Any]]:
    if not CLOSED_TRADES_FILE.exists():
        return []
    try:
        with CLOSED_TRADES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def classify_trade(trade: Dict[str, Any]) -> str:
    pnl = safe_float(trade.get("realized_pnl_usd"), 0.0)
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "FLAT"


def format_money(v: float) -> str:
    return f"${v:,.4f}"


def format_pct(v: float) -> str:
    return f"{v:.2f}%"


def get_asset_class(trade: Dict[str, Any]) -> str:
    asset_class = str(trade.get("asset_class", "UNKNOWN")).upper().strip()
    return asset_class or "UNKNOWN"


def analyze_attribution() -> None:
    trades = load_closed_trades()

    print("\n==============================================================")
    print(" CSS TRADE ATTRIBUTION ENGINE")
    print("==============================================================\n")

    if not trades:
        print("No closed trades yet. Attribution will activate once trades close.\n")
        return

    total = len(trades)
    wins = []
    losses = []
    flats = []

    total_net_pnl = 0.0
    total_gross_pnl = 0.0
    total_round_trip_cost = 0.0

    asset_breakdown: Dict[str, Dict[str, float]] = {}

    for t in trades:
        net_pnl = safe_float(t.get("realized_pnl_usd", t.get("net_realized_pnl_usd", 0.0)), 0.0)
        gross_pnl = safe_float(t.get("gross_realized_pnl_usd"), net_pnl)
        round_trip_cost = safe_float(t.get("total_round_trip_cost_usd"), 0.0)
        asset_class = get_asset_class(t)

        total_net_pnl += net_pnl
        total_gross_pnl += gross_pnl
        total_round_trip_cost += round_trip_cost

        if asset_class not in asset_breakdown:
            asset_breakdown[asset_class] = {
                "count": 0.0,
                "wins": 0.0,
                "losses": 0.0,
                "flats": 0.0,
                "gross_pnl": 0.0,
                "net_pnl": 0.0,
                "cost": 0.0,
            }

        asset_breakdown[asset_class]["count"] += 1.0
        asset_breakdown[asset_class]["gross_pnl"] += gross_pnl
        asset_breakdown[asset_class]["net_pnl"] += net_pnl
        asset_breakdown[asset_class]["cost"] += round_trip_cost

        if net_pnl > 0:
            wins.append(t)
            asset_breakdown[asset_class]["wins"] += 1.0
        elif net_pnl < 0:
            losses.append(t)
            asset_breakdown[asset_class]["losses"] += 1.0
        else:
            flats.append(t)
            asset_breakdown[asset_class]["flats"] += 1.0

    win_rate = (len(wins) / total * 100.0) if total else 0.0
    loss_rate = (len(losses) / total * 100.0) if total else 0.0
    flat_rate = (len(flats) / total * 100.0) if total else 0.0

    print(f"Total Closed Trades:        {total}")
    print(f"Wins:                       {len(wins)}")
    print(f"Losses:                     {len(losses)}")
    print(f"Flats:                      {len(flats)}")
    print(f"Win Rate:                   {format_pct(win_rate)}")
    print(f"Loss Rate:                  {format_pct(loss_rate)}")
    print(f"Flat Rate:                  {format_pct(flat_rate)}")

    print("\n---------------- FINANCIAL ATTRIBUTION ----------------\n")
    print(f"Total Gross Realized PnL:   {format_money(total_gross_pnl)}")
    print(f"Total Execution Cost Drag:  {format_money(total_round_trip_cost)}")
    print(f"Total Net Realized PnL:     {format_money(total_net_pnl)}")

    if total_gross_pnl != 0:
        cost_drag_pct = (total_round_trip_cost / abs(total_gross_pnl)) * 100.0
        print(f"Cost Drag vs Gross PnL:     {format_pct(cost_drag_pct)}")
    else:
        print("Cost Drag vs Gross PnL:     n/a")

    print("\n---------------- ASSET CLASS BREAKDOWN ----------------\n")

    if not asset_breakdown:
        print("No asset-class breakdown available.\n")
    else:
        for asset_class, stats in sorted(asset_breakdown.items()):
            count = safe_int(stats.get("count"), 0)
            wins_count = safe_int(stats.get("wins"), 0)
            losses_count = safe_int(stats.get("losses"), 0)
            flats_count = safe_int(stats.get("flats"), 0)
            gross_pnl = safe_float(stats.get("gross_pnl"), 0.0)
            net_pnl = safe_float(stats.get("net_pnl"), 0.0)
            cost = safe_float(stats.get("cost"), 0.0)

            print(
                f"{asset_class:10} "
                f"trades={count:<3} "
                f"wins={wins_count:<3} "
                f"losses={losses_count:<3} "
                f"flats={flats_count:<3} "
                f"gross={format_money(gross_pnl):>12} "
                f"cost={format_money(cost):>12} "
                f"net={format_money(net_pnl):>12}"
            )

    print("\n------------------ RECENT TRADE DETAILS ------------------\n")

    for t in trades[-15:]:
        symbol = str(t.get("symbol", "n/a"))
        asset_class = get_asset_class(t)
        net_pnl = safe_float(t.get("realized_pnl_usd", t.get("net_realized_pnl_usd", 0.0)), 0.0)
        gross_pnl = safe_float(t.get("gross_realized_pnl_usd"), net_pnl)
        round_trip_cost = safe_float(t.get("total_round_trip_cost_usd"), 0.0)
        reason = str(t.get("exit_reason", "n/a"))
        held = safe_int(t.get("cycles_held"), 0)

        classification = classify_trade(t)

        print(
            f"{symbol:12} "
            f"{asset_class:8} "
            f"{classification:6} "
            f"gross={format_money(gross_pnl):>10} "
            f"cost={format_money(round_trip_cost):>10} "
            f"net={format_money(net_pnl):>10} "
            f"reason={reason:>12} "
            f"held={held}"
        )

    print("\n------------------ INSIGHT ------------------\n")

    if losses and not wins:
        print("All net outcomes are losses so far. Signal quality and/or cost drag needs tightening.")
    elif wins and not losses:
        print("All net outcomes are wins so far. Good sign, but sample size still matters.")
    else:
        print("Mixed net outcomes. System is now in genuine validation mode with cost-aware attribution.")

    print("\n==============================================================\n")


if __name__ == "__main__":
    analyze_attribution()