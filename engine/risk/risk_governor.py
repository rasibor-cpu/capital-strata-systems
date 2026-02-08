"""
Risk Governor – Core Enforcement Layer
REA Capital Trading Engine

Integrated Micro Mode support (toggle via REA_MICRO_MODE=1)
Dynamic Daily Drawdown based on % of equity
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


ALLOW = "ALLOW"
BLOCK = "BLOCK"


# ============================================================
# Policy Definitions
# ============================================================

@dataclass(frozen=True)
class RiskPolicy:
    name: str
    max_trades_per_day: int
    max_concurrent_positions: int
    max_consecutive_losses: int
    max_losses_per_pair: int
    cooldown_hours: int
    max_equity_risk_per_trade: float
    max_daily_drawdown_pct: float


def micro_mode_enabled() -> bool:
    return os.environ.get("REA_MICRO_MODE", "0") == "1"


def load_policy() -> RiskPolicy:
    if micro_mode_enabled():
        return RiskPolicy(
            name="MICRO_MODE",
            max_trades_per_day=5,
            max_concurrent_positions=3,
            max_consecutive_losses=3,
            max_losses_per_pair=2,
            cooldown_hours=12,
            max_equity_risk_per_trade=0.01,
            max_daily_drawdown_pct=0.03,   # 3%
        )

    return RiskPolicy(
        name="NORMAL",
        max_trades_per_day=15,
        max_concurrent_positions=20,
        max_consecutive_losses=5,
        max_losses_per_pair=3,
        cooldown_hours=12,
        max_equity_risk_per_trade=0.02,
        max_daily_drawdown_pct=0.05,      # 5%
    )


# ============================================================
# Governor
# ============================================================

class RiskGovernor:

    def __init__(self):
        self.policy = load_policy()

    def refresh(self):
        self.policy = load_policy()

    def _utc_today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _equity_base(self) -> float:
        return float(os.environ.get("REA_DEFAULT_EQUITY", "10000"))

    def evaluate(
        self,
        *,
        instrument: str,
        equity_risk: Optional[float],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        self.refresh()
        p = self.policy

        # Self-heal state schema
        state.setdefault("daily_pnl", 0.0)
        state.setdefault("cooldown_until", None)

        required = [
            "day_key",
            "trades_today",
            "open_positions",
            "consecutive_losses",
            "losses_by_pair",
        ]

        for r in required:
            if r not in state:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": [f"Missing state field: {r}"],
                }

        # Daily reset
        today = self._utc_today()
        if state["day_key"] != today:
            state["day_key"] = today
            state["trades_today"] = 0
            state["consecutive_losses"] = 0
            state["losses_by_pair"] = {}
            state["cooldown_until"] = None
            state["daily_pnl"] = 0.0

        # Dynamic Daily Drawdown
        equity = self._equity_base()
        max_drawdown = equity * p.max_daily_drawdown_pct

        if state["daily_pnl"] <= -max_drawdown:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Daily drawdown limit reached"],
            }

        # Cooldown
        cd = state.get("cooldown_until")
        if cd:
            until = datetime.fromisoformat(cd)
            if datetime.now(timezone.utc) < until:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": [f"Cooldown active until {cd}"],
                }

        # Hard limits
        if state["trades_today"] >= p.max_trades_per_day:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Max trades per day reached"],
            }

        if state["open_positions"] >= p.max_concurrent_positions:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Max concurrent positions reached"],
            }

        if state["consecutive_losses"] >= p.max_consecutive_losses:
            until = datetime.now(timezone.utc) + timedelta(hours=p.cooldown_hours)
            state["cooldown_until"] = until.isoformat()
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Consecutive loss cap hit – cooldown engaged"],
            }

        pair_losses = state["losses_by_pair"].get(instrument, 0)
        if pair_losses >= p.max_losses_per_pair:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Instrument loss cap reached"],
            }

        # Per-trade equity risk cap
        if equity_risk is not None:
            if equity_risk > p.max_equity_risk_per_trade:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": ["Equity risk exceeds policy cap"],
                }

        return {
            "decision": ALLOW,
            "policy": p.name,
            "reasons": ["Risk checks passed"],
        }


# ============================================================
# State Updates
# ============================================================

def apply_trade(state: Dict[str, Any]) -> Dict[str, Any]:
    state["trades_today"] += 1
    state["open_positions"] += 1
    return state


def apply_result(state: Dict[str, Any], instrument: str, pnl: float) -> Dict[str, Any]:

    state["daily_pnl"] += pnl
    state["open_positions"] = max(0, state["open_positions"] - 1)

    if pnl < 0:
        state["consecutive_losses"] += 1
        state["losses_by_pair"][instrument] = (
            state["losses_by_pair"].get(instrument, 0) + 1
        )
    else:
        state["consecutive_losses"] = 0

    return state
