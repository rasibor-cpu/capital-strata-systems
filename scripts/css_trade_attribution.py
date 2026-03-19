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
    reason = str(trade.get("exit_reason", "")).upper()

    # Default fallback (since we don't yet persist signal metadata)
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "FLAT"


def format_money(v: float) -> str:
    return f"${v:,.4f}"


def analyze_attribution() -> None:
    trades = load_closed_trades()

    print("\n==================================================")
    print(" CSS TRADE ATTRIBUTION ENGINE")
    print("==================================================\n")

    if not trades:
        print("No closed trades yet. Attribution will activate once trades close.\n")
        return

    total = len(trades)
    wins = []
    losses = []

    for t in trades:
        pnl = safe_float(t.get("realized_pnl_usd"), 0.0)
        if pnl > 0:
            wins.append(t)
        elif pnl < 0:
            losses.append(t)

    print(f"Total Closed Trades: {total}")
    print(f"Wins:                {len(wins)}")
    print(f"Losses:              {len(losses)}")

    print("\n------------------ TRADE DETAILS ------------------\n")

    for t in trades[-15:]:
        symbol = t.get("symbol", "n/a")
        pnl = safe_float(t.get("realized_pnl_usd"), 0.0)
        reason = t.get("exit_reason", "n/a")
        held = safe_int(t.get("cycles_held"), 0)

        classification = classify_trade(t)

        print(
            f"{symbol:12} "
            f"{classification:6} "
            f"pnl={format_money(pnl):>10} "
            f"reason={reason:>4} "
            f"held={held}"
        )

    print("\n------------------ INSIGHT ------------------\n")

    if losses and not wins:
        print("All losses so far → signals may still be too permissive.")
    elif wins and not losses:
        print("All wins so far → rare but strong signal filtering.")
    else:
        print("Mixed outcomes → system entering validation phase.")

    print("\n==================================================\n")


if __name__ == "__main__":
    analyze_attribution()