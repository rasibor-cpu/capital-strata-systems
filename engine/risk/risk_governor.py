"""
Risk Governor – Core Enforcement Layer
REA Capital Trading Engine

Integrated Micro Mode support (toggle via REA_MICRO_MODE=1)

NOTE:
We are keeping Micro Mode + persistence inside this file for now.
Later we will extract Micro Mode into a separate policy layer module
and persistence into a dedicated store module.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


ALLOW = "ALLOW"
BLOCK = "BLOCK"

_STATE_FILE = Path("engine/risk/risk_state.json")


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
# Persistent State
# ============================================================

def _default_state() -> Dict[str, Any]:
    return {
        "day_key": "",
        "trades_today": 0,
        "open_positions": 0,
        "consecutive_losses": 0,
        "losses_by_pair": {},
        "cooldown_until": None,  # ISO8601 string or None
    }


def _load_state_from_disk() -> Dict[str, Any]:
    if not _STATE_FILE.exists():
        return _default_state()

    try:
        with _STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # merge defaults to survive schema evolution
        base = _default_state()
        if isinstance(data, dict):
            base.update(data)
        return base
    except Exception:
        # Fail closed-ish: revert to defaults if corrupted file
        return _default_state()


def _save_state_to_disk(state: Dict[str, Any]) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
    except Exception:
        # Never crash engine because state couldn't persist
        return


def _utc_today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_dt_iso(s: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ============================================================
# Governor
# ============================================================

class RiskGovernor:
    """
    RiskGovernor evaluates a proposed trade against policy + running state.

    IMPORTANT:
    - By default it uses a persistent internal state (engine/risk/risk_state.json).
    - For backwards compatibility with earlier experiments, you may pass a
      state dict into evaluate(..., state=...) and it will use that state
      for the evaluation. In that case, persistence is NOT guaranteed unless
      you also copy it into rg.state and/or call rg.save_state().
    """

    def __init__(self):
        self.policy: RiskPolicy = load_policy()
        self.state: Dict[str, Any] = _load_state_from_disk()

    def refresh(self) -> None:
        self.policy = load_policy()

    def save_state(self) -> None:
        _save_state_to_disk(self.state)

    def get_state(self) -> Dict[str, Any]:
        # return a shallow copy so callers don't mutate silently
        return dict(self.state)

    def set_open_positions(self, n: int) -> None:
        # helper for integration with execution/order routing layer
        try:
            self.state["open_positions"] = max(0, int(n))
        except Exception:
            self.state["open_positions"] = 0
        self.save_state()

    def _daily_reset_if_needed(self, state: Dict[str, Any]) -> None:
        today = _utc_today_key()
        if state.get("day_key") != today:
            state["day_key"] = today
            state["trades_today"] = 0
            state["consecutive_losses"] = 0
            state["losses_by_pair"] = {}
            state["cooldown_until"] = None

    def evaluate(
        self,
        *,
        instrument: str,
        equity_risk: Optional[float],
        state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            "decision": "ALLOW" | "BLOCK",
            "policy": "MICRO_MODE" | "NORMAL",
            "reasons": [ ... ]
          }
        """
        self.refresh()
        p = self.policy

        # Use passed state if provided, else internal persistent state.
        st = state if isinstance(state, dict) else self.state

        # Validate state (fail closed)
        required = [
            "day_key",
            "trades_today",
            "open_positions",
            "consecutive_losses",
            "losses_by_pair",
        ]
        for r in required:
            if r not in st:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": [f"Missing state field: {r}"],
                }

        # Daily reset (UTC)
        self._daily_reset_if_needed(st)

        # Cooldown check
        cd = st.get("cooldown_until")
        if cd:
            until = _parse_dt_iso(cd)
            if until is None:
                # corrupt cooldown value -> fail closed: block and clear
                st["cooldown_until"] = None
                if st is self.state:
                    self.save_state()
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": ["Cooldown value invalid; cleared and blocked once"],
                }

            if datetime.now(timezone.utc) < until:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": [f"Cooldown active until {cd}"],
                }

        # Hard Limits
        if int(st["trades_today"]) >= p.max_trades_per_day:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Max trades per day reached"],
            }

        if int(st["open_positions"]) >= p.max_concurrent_positions:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Max concurrent positions reached"],
            }

        if int(st["consecutive_losses"]) >= p.max_consecutive_losses:
            until = datetime.now(timezone.utc) + timedelta(hours=p.cooldown_hours)
            st["cooldown_until"] = until.isoformat()
            if st is self.state:
                self.save_state()
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Consecutive loss cap hit – cooldown engaged"],
            }

        pair_losses = int(st["losses_by_pair"].get(instrument, 0))
        if pair_losses >= p.max_losses_per_pair:
            return {
                "decision": BLOCK,
                "policy": p.name,
                "reasons": ["Instrument loss cap reached"],
            }

        # Equity Risk Cap
        if equity_risk is not None:
            try:
                if float(equity_risk) > p.max_equity_risk_per_trade:
                    return {
                        "decision": BLOCK,
                        "policy": p.name,
                        "reasons": ["Equity risk exceeds policy cap"],
                    }
            except Exception:
                return {
                    "decision": BLOCK,
                    "policy": p.name,
                    "reasons": ["Invalid equity_risk value"],
                }

        # Persist daily reset, etc. if using internal state.
        if st is self.state:
            self.save_state()

        return {
            "decision": ALLOW,
            "policy": p.name,
            "reasons": ["Risk checks passed"],
        }


# ============================================================
# State Update Helpers (Persistent if used with RiskGovernor.state)
# ============================================================

def apply_trade(state: Dict[str, Any]) -> Dict[str, Any]:
    state["trades_today"] = int(state.get("trades_today", 0)) + 1
    return state


def apply_result(state: Dict[str, Any], instrument: str, pnl: float) -> Dict[str, Any]:
    if pnl < 0:
        state["consecutive_losses"] = int(state.get("consecutive_losses", 0)) + 1
        losses = state.get("losses_by_pair", {})
        if not isinstance(losses, dict):
            losses = {}
        losses[instrument] = int(losses.get(instrument, 0)) + 1
        state["losses_by_pair"] = losses
    else:
        state["consecutive_losses"] = 0
    return state
