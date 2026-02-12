"""
Capital Strata Systems
Risk Governor – Governance Enforcement Layer

Global Controls:
- Daily 5% cap
- Rolling peak global drawdown (5% first 30 days → 7% after)
- Mode-based limits (live/demo/micro)
- Manual reset required for global lock
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List


ALLOW = "ALLOW"
BLOCK = "BLOCK"


# ==========================================================
# Mode Policy Definitions
# ==========================================================

@dataclass(frozen=True)
class ModePolicy:
    name: str
    max_trades_per_day: int
    max_consecutive_losses: int
    cooldown_minutes: int
    daily_loss_cap_pct: float
    position_scale: float


MODE_POLICIES: Dict[str, ModePolicy] = {
    "live": ModePolicy("live", 20, 10, 60, 0.05, 1.0),
    "demo": ModePolicy("demo", 10, 5, 30, 0.05, 1.0),
    "micro": ModePolicy("micro", 10, 5, 20, 0.05, 0.25),
}


# ==========================================================
# Global Drawdown Settings
# ==========================================================

INITIAL_GLOBAL_DD_LIMIT = 0.05   # 5% first 30 days
EXPANDED_GLOBAL_DD_LIMIT = 0.07  # 7% after 30 days
DD_EXPANSION_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_key_utc() -> str:
    return _utc_now().strftime("%Y-%m-%d")


def _ensure_day_roll(state: Dict[str, Any]) -> None:
    if state.get("day_key") != _day_key_utc():
        state["day_key"] = _day_key_utc()
        state["trades_today"] = 0
        state["daily_pnl"] = 0.0
        state["consecutive_losses"] = 0
        state["cooldown_until"] = None
        state["daily_shutdown"] = False
        state["daily_shutdown_reason"] = ""


def _ensure_inception(state: Dict[str, Any]) -> None:
    """
    Sets system inception timestamp if not already defined.
    This persists across runs if you store state.
    """
    if state.get("system_inception_utc") is None:
        state["system_inception_utc"] = _utc_now().isoformat()


def _get_global_dd_limit(state: Dict[str, Any]) -> float:
    """
    Returns the correct drawdown limit depending on age of system.
    """
    inception_str = state.get("system_inception_utc")
    if not inception_str:
        return INITIAL_GLOBAL_DD_LIMIT

    inception = datetime.fromisoformat(inception_str)
    days_running = (_utc_now() - inception).days

    if days_running >= DD_EXPANSION_DAYS:
        return EXPANDED_GLOBAL_DD_LIMIT

    return INITIAL_GLOBAL_DD_LIMIT


def apply_trade(state: Dict[str, Any]) -> None:
    _ensure_day_roll(state)
    state["trades_today"] = int(state.get("trades_today") or 0) + 1


def apply_result(state: Dict[str, Any], *, instrument: str, pnl: float) -> None:
    _ensure_day_roll(state)

    state["daily_pnl"] = float(state.get("daily_pnl") or 0.0) + pnl

    if pnl < 0:
        state["consecutive_losses"] = int(state.get("consecutive_losses") or 0) + 1
    else:
        state["consecutive_losses"] = 0


class RiskGovernor:

    def __init__(self):
        mode = os.getenv("CS_MODE", "demo").lower()
        if mode not in MODE_POLICIES:
            mode = "demo"
        self.policy = MODE_POLICIES[mode]

    def evaluate(
        self,
        *,
        instrument: str,
        equity_risk: float,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        _ensure_day_roll(state)
        _ensure_inception(state)

        reasons: List[str] = []

        # --- Rolling Peak Tracking ---
        if state.get("equity_peak") is None:
            state["equity_peak"] = equity_risk
        else:
            state["equity_peak"] = max(state["equity_peak"], equity_risk)

        peak = float(state["equity_peak"])
        current = float(equity_risk)

        # --- Global Drawdown ---
        dd_limit = _get_global_dd_limit(state)
        drawdown = (peak - current) / peak if peak > 0 else 0.0

        if state.get("global_shutdown"):
            return {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state.get("global_shutdown_reason") or "Global shutdown active"],
            }

        if drawdown >= dd_limit:
            state["global_shutdown"] = True
            state["global_shutdown_reason"] = (
                f"Global drawdown {drawdown:.2%} exceeded {dd_limit:.0%} limit."
            )
            return {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state["global_shutdown_reason"]],
            }

        # --- Daily Loss Cap ---
        if state.get("daily_start_equity") is None:
            state["daily_start_equity"] = equity_risk

        start_eq = float(state["daily_start_equity"])
        loss_floor = start_eq * (1 - self.policy.daily_loss_cap_pct)

        if current <= loss_floor:
            state["daily_shutdown"] = True
            state["daily_shutdown_reason"] = "Daily loss cap breached."
            return {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state["daily_shutdown_reason"]],
            }

        if state.get("daily_shutdown"):
            return {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state.get("daily_shutdown_reason")],
            }

        # --- Cooldown ---
        cd = state.get("cooldown_until")
        if cd:
            if datetime.fromisoformat(cd) > _utc_now():
                return {
                    "decision": BLOCK,
                    "policy": self.policy.name,
                    "reasons": ["Cooldown active"],
                }
            else:
                state["cooldown_until"] = None

        # --- Max trades per day ---
        if int(state.get("trades_today") or 0) >= self.policy.max_trades_per_day:
            return {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": ["Max trades/day reached"],
            }

        # --- Loss streak ---
        if int(state.get("consecutive_losses") or 0) >= self.policy.max_consecutive_losses:
            state["cooldown_until"] = (
                _utc_now() + timedelta(minutes=self.policy.cooldown_minutes)
            ).isoformat()
            return {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": ["Loss streak limit hit → cooldown"],
            }

        return {
            "decision": ALLOW,
            "policy": self.policy.name,
            "reasons": ["approved"],
        }
