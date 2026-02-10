"""
Equity Drawdown Guard – REA Capital Trading Engine
--------------------------------------------------

Purpose:
- Protect total capital from catastrophic erosion.
- Block trading if equity drawdown exceeds configured threshold.
- Fail-closed: missing equity data => BLOCK.

"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class EquityDrawdownPolicy:
    max_drawdown_pct: float = 25.0  # 25% cap


def evaluate_equity_drawdown(
    current_equity: float | None,
    peak_equity: float | None,
    policy: EquityDrawdownPolicy,
) -> dict:

    timestamp = datetime.now(timezone.utc).isoformat()

    if current_equity is None or peak_equity is None:
        return {
            "decision": "BLOCK",
            "reason": "Equity data missing (fail-closed).",
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "drawdown_pct": None,
            "max_drawdown_pct": policy.max_drawdown_pct,
            "allowed": False,
            "timestamp_utc": timestamp,
        }

    if peak_equity <= 0:
        return {
            "decision": "BLOCK",
            "reason": "Invalid peak equity value.",
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "drawdown_pct": None,
            "max_drawdown_pct": policy.max_drawdown_pct,
            "allowed": False,
            "timestamp_utc": timestamp,
        }

    drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100

    if drawdown_pct >= policy.max_drawdown_pct:
        return {
            "decision": "BLOCK",
            "reason": "Max equity drawdown exceeded.",
            "current_equity": current_equity,
            "peak_equity": peak_equity,
            "drawdown_pct": round(drawdown_pct, 2),
            "max_drawdown_pct": policy.max_drawdown_pct,
            "allowed": False,
            "timestamp_utc": timestamp,
        }

    return {
        "decision": "ALLOW",
        "reason": "Drawdown within limits.",
        "current_equity": current_equity,
        "peak_equity": peak_equity,
        "drawdown_pct": round(drawdown_pct, 2),
        "max_drawdown_pct": policy.max_drawdown_pct,
        "allowed": True,
        "timestamp_utc": timestamp,
    }
