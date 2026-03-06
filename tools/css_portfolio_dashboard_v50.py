"""
Capital Strata Systems
Portfolio Dashboard v50

Reads CSS state and trade history, then prints a concise portfolio dashboard.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STATE_DIR = Path("backend/state")
LOG_DIR = Path("audit_logs")
TRADE_HISTORY = LOG_DIR / "trade_history.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def open_positions() -> list[dict]:
    positions: list[dict] = []

    for f in STATE_DIR.glob("pos_*.json"):
        data = load_json(f, None)
        if not isinstance(data, dict):
            continue
        if data.get("status") == "OPEN":
            positions.append(data)

    return positions


def closed_trades() -> list[dict]:
    history = load_json(TRADE_HISTORY, [])
    if not isinstance(history, list):
        return []
    return [x for x in history if isinstance(x, dict)]


def portfolio_risk(open_pos: list[dict]) -> float:
    total = 0.0

    for p in open_pos:
        try:
            entry = float(p["entry"])
            stop = float(p["stop"])
            size = float(p["size"])
            total += max(0.0, (entry - stop) * size)
        except Exception:
            continue

    return total


def stats(trades: list[dict]) -> dict:
    if not trades:
        return {
            "count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "net_pnl": 0.0,
            "profit_factor": 0.0,
            "best_asset": "N/A",
            "worst_asset": "N/A",
        }

    wins = [t for t in trades if float(t.get("pnl", 0)) > 0]
    losses = [t for t in trades if float(t.get("pnl", 0)) <= 0]

    gross_profit = sum(float(t.get("pnl", 0)) for t in wins)
    gross_loss_abs = abs(sum(float(t.get("pnl", 0)) for t in losses))
    net_pnl = sum(float(t.get("pnl", 0)) for t in trades)

    by_asset: dict[str, float] = {}
    for t in trades:
        asset = str(t.get("asset", "UNKNOWN"))
        by_asset[asset] = by_asset.get(asset, 0.0) + float(t.get("pnl", 0))

    best_asset = max(by_asset, key=by_asset.get) if by_asset else "N/A"
    worst_asset = min(by_asset, key=by_asset.get) if by_asset else "N/A"

    return {
        "count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss_abs,
        "net_pnl": net_pnl,
        "profit_factor": (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else 0.0,
        "best_asset": best_asset,
        "worst_asset": worst_asset,
    }


def print_dashboard() -> None:
    open_pos = open_positions()
    trades = closed_trades()
    s = stats(trades)
    live_risk = portfolio_risk(open_pos)

    print("\n" + "=" * 44)
    print("CSS PORTFOLIO DASHBOARD v50")
    print("=" * 44)

    print("\nLIVE PORTFOLIO")
    print(f"Open positions      : {len(open_pos)}")
    print(f"Live portfolio risk : ${live_risk:.2f}")

    print("\nCLOSED TRADE HISTORY")
    print(f"Closed trades       : {s['count']}")
    print(f"Wins                : {s['wins']}")
    print(f"Losses              : {s['losses']}")
    print(f"Win rate            : {s['win_rate'] * 100:.2f}%")
    print(f"Gross profit        : ${s['gross_profit']:.2f}")
    print(f"Gross loss          : ${s['gross_loss']:.2f}")
    print(f"Net PnL             : ${s['net_pnl']:.2f}")
    print(f"Profit factor       : {s['profit_factor']:.2f}")

    print("\nASSET LEADERS")
    print(f"Best asset          : {s['best_asset']}")
    print(f"Worst asset         : {s['worst_asset']}")

    print("\nOPEN POSITIONS DETAIL")
    if not open_pos:
        print("None")
    else:
        for p in open_pos:
            asset = p.get("asset", "UNKNOWN")
            strategy = p.get("strategy", "UNKNOWN")
            entry = float(p.get("entry", 0))
            stop = float(p.get("stop", 0))
            size = float(p.get("size", 0))
            print(
                f"- {asset} | {strategy} | entry {entry:.6f} | "
                f"stop {stop:.6f} | size {size:.4f}"
            )

    print("")


if __name__ == "__main__":
    print_dashboard()