"""
Risk Governor – Core Enforcement Layer
REA Capital Trading Engine

Integrated Micro Mode support (toggle via REA_MICRO_MODE=1)

NOTE:
We are keeping Micro Mode inside this file for now.
Later we will extract it into a separate policy layer module.
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


def micro_mode_enabled() -> bool:
    return os.environ.get("REA_MICRO_MODE", "0") == "1"


def load_policy() -> RiskPolicy:
    # Micro Mode: tighter caps for paper testing / early validation
    if micro_mode_enabled():
        return RiskPolicy(
            name="MICRO_MODE",
            max_trades_per_day=5,
            max_concurrent_positions=3,
            max_consecutive_losses=3,
            max_losses_per_pair=2,
            cooldown_hours=12,
            max_equity_risk_per_trade=0.01,
        )

    # Normal (Phase 1 defaults)
    return RiskPolicy(
        name="NORMAL",
        max_trades_per_day=15,
        max_concurrent_positions=20,
        max_consecutive_losses=5,
        max_losses_per_pair=3,
        cooldown_hours=12,
        max_equity_risk_per_trade=0.02,
    )


# ============================================================
# State Schema (self-heal older state dictionaries)
# ============================================================

def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ensure_state_schema(state: Dict[str, Any]) -> None:
    """
    Phase-1 compatibility shim:
    - Older state dicts may not contain newer keys (e.g. daily_pnl).
    - We fail-closed for truly missing critical fields by initializing safe defaults.
    """
    state.setdefault("day_key", "1970-01-01")
    state.setdefault("trades_today", 0)
    state.setdefault("open_positions", 0)
    state.setdefault("consecutive_losses", 0)
    state.setdefault("losses_by_pair", {})
    state.setdefault("cooldown_until", None)

    # NEW: track realized PnL per UTC day (prevents KeyError)
    state.setdefault("daily_pnl", 0.0)

    # Defensive normalization
    if state.get("losses_by_pair") is None:
        state["losses_by_pair"] = {}
    if not isinstance(state.get("losses_by_pair"), dict):
        state["losses_by_pair"] = {}


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
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        self.refresh()
        p = self.policy

        # Ensure state has all required keys (prevents KeyError across versions)
        ensure_state_schema(state)

        # Daily reset (UTC) — DO NOT reset open_positions (positions can carry overnight)
        today = _utc_today()
        if state["day_key"] != today:
            state["day_key"] = today
            state["trades_today"] = 0
            state["consecutive_losses"] = 0
            state["losses_by_pair"] = {}
            state["cooldown_until"] = None
            state["daily_pnl"] = 0.0

        # Cooldown check
        cd = state.get("cooldown_until")
        if cd:
            try:
                until = datetime.fromisoformat(cd)
            except Exception:
                # Corrupt cooldown timestamp => fail closed
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": [f"Invalid cooldown_until timestamp: {cd!r}"],
                }

            if datetime.now(timezone.utc) < until:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": [f"Cooldown active until {cd}"],
                }

        # Hard Limits
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

        # Equity Risk Cap
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
# State Update Helpers
# ============================================================

def apply_trade(state: Dict[str, Any]) -> Dict[str, Any]:
    ensure_state_schema(state)
    state["trades_today"] += 1
    return state


def apply_result(state: Dict[str, Any], instrument: str, pnl: float) -> Dict[str, Any]:
    """
    Record a realized result for the instrument.
    This is called after a trade is closed (or after a test PnL is produced).
    """
    ensure_state_schema(state)

    # Daily realized pnl
    state["daily_pnl"] += float(pnl)

    if pnl < 0:
        state["consecutive_losses"] += 1
        state["losses_by_pair"][instrument] = state["losses_by_pair"].get(instrument, 0) + 1
    else:
        # Win resets consecutive loss streak
        state["consecutive_losses"] = 0

    return state
