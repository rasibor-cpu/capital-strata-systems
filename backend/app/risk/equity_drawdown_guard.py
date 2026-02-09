"""
Equity Drawdown Guard – REA Capital Trading Engine
--------------------------------------------------

Purpose:
- Enforce global equity drawdown cap
- Enforce per-trade risk cap
- Block or require override for excessive risk

Safe Default:
- Missing equity data => BLOCK
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class EquityDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_OVERRIDE = "REQUIRE_OVERRIDE"


@dataclass(frozen=True)
class EquityPolicy:
    max_drawdown_pct: float = 0.25        # 25%
    max_trade_risk_pct: float = 0.20      # 20% per trade


@dataclass
class EquitySnapshot:
    current_equity: float
    peak_equity: float
    requested_trade_risk: float


def evaluate_equity_risk(
    snapshot: EquitySnapshot,
    policy: EquityPolicy = EquityPolicy(),
) -> dict:

    now = datetime.now(timezone.utc)

    if (
        snapshot.current_equity <= 0
        or snapshot.peak_equity <= 0
    ):
        return {
            "decision": EquityDecision.BLOCK,
            "reason": "Invalid equity values",
            "timestamp_utc": now,
        }

    drawdown_pct = (
        (snapshot.peak_equity - snapshot.current_equity)
        / snapshot.peak_equity
    )

    trade_risk_pct = (
        snapshot.requested_trade_risk
        / snapshot.current_equity
        if snapshot.current_equity > 0
        else 1.0
    )

    if drawdown_pct >= policy.max_drawdown_pct:
        return {
            "decision": EquityDecision.BLOCK,
            "reason": "Max drawdown exceeded",
            "drawdown_pct": drawdown_pct,
            "timestamp_utc": now,
        }

    if trade_risk_pct > policy.max_trade_risk_pct:
        return {
            "decision": EquityDecision.REQUIRE_OVERRIDE,
            "reason": "Trade risk exceeds 20% equity",
            "trade_risk_pct": trade_risk_pct,
            "timestamp_utc": now,
        }

    return {
        "decision": EquityDecision.ALLOW,
        "reason": "Within equity limits",
        "drawdown_pct": drawdown_pct,
        "trade_risk_pct": trade_risk_pct,
        "timestamp_utc": now,
    }
