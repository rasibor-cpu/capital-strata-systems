"""
Risk Governor – Core Enforcement Layer
REA Capital Trading Engine

Phase 1 Fully Hardened:
- Defensive state schema
- Consecutive loss caps
- Instrument loss caps
- Daily trade caps
- Concurrent position caps
- Equity risk caps
- Daily drawdown kill-switch
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


ALLOW = "ALLOW"
BLOCK = "BLOCK"


# ============================================================
# Policy
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
            max_daily_drawdown_pct=0.03,  # 3%
        )

    return RiskPolicy(
        name="NORMAL",
        max_trades_per_day=15,
        max_concurrent_positions=20,
        max_consecutive_losses=5,
        max_losses_per_pair=3,
        cooldown_hours=12,
        max_equity_risk_per_trade=0.02,
        max_daily_drawdown_pct=0.10,  # 10%
    )


# ============================================================
# State Integrity
# ============================================================

def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ensure_state_schema(state: Dict[str, Any]) -> None:
    defaults = {
        "day_key": "1970-01-01",
        "trades_today": 0,
        "open_positions": 0,
        "consecutive_losses": 0,
        "losses_by_pair": {},
        "cooldown_until": None,
        "daily_pnl": 0.0,
    }

    for k, v in defaults.items():
        state.setdefault(k, v)

    state["trades_today"] = max(int(state["trades_today"]), 0)
    state["open_positions"] = max(int(state["open_positions"]), 0)
    state["consecutive_losses"] = max(int(state["consecutive_losses"]), 0)
    state["daily_pnl"] = float(state["daily_pnl"])

    if not isinstance(state["losses_by_pair"], dict):
        state["losses_by_pair"] = {}

    clean = {}
    for k, v in state["losses_by_pair"].items():
        try:
            clean[str(k)] = max(int(v), 0)
        except Exception:
            clean[str(k)] = 0

    state["losses_by_pair"] = clean


# ============================================================
# Governor
# ============================================================

class RiskGovernor:

    def __init__(self):
        self.policy = load_policy()

    def refresh(self):
        self.policy = load_policy()

    def evaluate(
        self,
        *,
        instrument: str,
        equity_risk: Optional[float],
        equity: float,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        self.refresh()
        p = self.policy

        ensure_state_schema(state)

        # Daily reset
        today = _utc_today()
        if state["day_key"] != today:
            state["day_key"] = today
            state["trades_today"] = 0
            state["consecutive_losses"] = 0
            state["losses_by_pair"] = {}
            state["cooldown_until"] = None
            state["daily_pnl"] = 0.0

        # 🔴 DAILY DRAWDOWN KILL SWITCH
        if equity > 0:
            drawdown_pct = abs(state["daily_pnl"]) / equity
            if state["daily_pnl"] < 0 and drawdown_pct >= p.max_daily_drawdown_pct:
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

        if state["losses_by_pair"].get(instrument, 0) >= p.max_losses_per_pair:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Instrument loss cap reached"],
            }

        if equity_risk is not None and equity_risk > p.max_equity_risk_per_trade:
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
    ensure_state_schema(state)
    state["trades_today"] += 1
    state["open_positions"] += 1
    return state


def apply_result(state: Dict[str, Any], instrument: str, pnl: float) -> Dict[str, Any]:
    ensure_state_schema(state)

    state["open_positions"] = max(state["open_positions"] - 1, 0)
    state["daily_pnl"] += float(pnl)

    if pnl < 0:
        state["consecutive_losses"] += 1
        state["losses_by_pair"][instrument] = (
            state["losses_by_pair"].get(instrument, 0) + 1
        )
    else:
        state["consecutive_losses"] = 0

    return state
