"""
Capital Strata Systems
Risk Governor – Governance Enforcement Layer

Global Controls:
- Daily 5% cap (mode policy daily_loss_cap_pct)
- Rolling peak global drawdown kill switch (default 5% from rolling peak)
- Mode-based limits (live/demo/micro)
- Manual reset required for global lock (via reset_global_lock script)

Note on "max global drawdown":
- This is the MAX allowed drawdown from the *rolling equity peak*.
- Example (5%): if peak equity = 100,000 then kill-switch triggers at <= 95,000.
- You can raise this later (e.g., to 7%) by setting: CS_GLOBAL_DD_LIMIT=0.07
"""

from __future__ import annotations

import json
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


# Global rolling-peak drawdown kill-switch (default 5%).
# When you're ready (e.g., after ~30 days), set CS_GLOBAL_DD_LIMIT=0.07
def _global_dd_limit() -> float:
    raw = (os.getenv("CS_GLOBAL_DD_LIMIT") or "0.05").strip()
    try:
        v = float(raw)
    except Exception:
        v = 0.05
    # guard rails
    if v < 0.01:
        v = 0.01
    if v > 0.25:
        v = 0.25
    return v


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _day_key_utc() -> str:
    return _utc_now().strftime("%Y-%m-%d")


def _append_journal(entry: Dict[str, Any]) -> None:
    """
    Append JSONL record to execution_journal.log in repo root.
    Fail-safe: never crash risk checks due to logging.
    """
    try:
        line = json.dumps(entry, ensure_ascii=False)
        with open("execution_journal.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _ensure_day_roll(state: Dict[str, Any]) -> None:
    """
    Resets *daily* counters at UTC day boundary.
    """
    if state.get("day_key") != _day_key_utc():
        state["day_key"] = _day_key_utc()
        state["trades_today"] = 0
        state["daily_pnl"] = 0.0
        state["consecutive_losses"] = 0
        state["cooldown_until"] = None
        state["daily_shutdown"] = False
        state["daily_shutdown_reason"] = ""
        # daily start equity resets at first evaluation of the day
        state["daily_start_equity"] = None


def apply_trade(state: Dict[str, Any]) -> None:
    _ensure_day_roll(state)
    state["trades_today"] = int(state.get("trades_today") or 0) + 1


def apply_result(state: Dict[str, Any], *, instrument: str, pnl: float) -> None:
    _ensure_day_roll(state)

    state["daily_pnl"] = float(state.get("daily_pnl") or 0.0) + float(pnl)

    if pnl < 0:
        state["consecutive_losses"] = int(state.get("consecutive_losses") or 0) + 1
    else:
        state["consecutive_losses"] = 0


class RiskGovernor:
    """
    Stateless policy + stateful enforcement via the supplied `state` dict.
    """

    def __init__(self):
        mode = (os.getenv("CS_MODE") or "demo").strip().lower()
        if mode not in MODE_POLICIES:
            mode = "demo"
        self.mode = mode
        self.policy = MODE_POLICIES[mode]
        self.global_dd_limit = _global_dd_limit()

    def evaluate(self, *, instrument: str, equity_risk: float, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        equity_risk is treated as CURRENT EQUITY (float).
        """
        _ensure_day_roll(state)

        reasons: List[str] = []

        # --------------------------------------------------
        # GLOBAL LOCK (manual reset required)
        # --------------------------------------------------
        if state.get("global_shutdown"):
            out = {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state.get("global_shutdown_reason") or "Global shutdown active"],
            }
            _append_journal({
                "type": "decision",
                "timestamp_utc": _utc_now_iso(),
                "instrument": instrument,
                "decision": out["decision"],
                "policy": out["policy"],
                "reasons": out["reasons"],
                "equity": round(float(equity_risk), 6),
                "equity_peak": round(float(state.get("equity_peak") or 0.0), 6),
                "mode": self.mode,
            })
            return out

        # --------------------------------------------------
        # Rolling equity peak tracking (global)
        # --------------------------------------------------
        current_equity = float(equity_risk)

        if state.get("equity_peak") is None:
            state["equity_peak"] = current_equity
        else:
            state["equity_peak"] = max(float(state["equity_peak"]), current_equity)

        equity_peak = float(state["equity_peak"])
        dd = (equity_peak - current_equity) / equity_peak if equity_peak > 0 else 0.0

        if dd >= self.global_dd_limit:
            state["global_shutdown"] = True
            state["global_shutdown_reason"] = (
                f"GLOBAL DRAWDOWN HIT: {dd:.2%} >= {self.global_dd_limit:.2%} "
                f"(peak={equity_peak:.2f}, equity={current_equity:.2f})"
            )
            out = {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state["global_shutdown_reason"]],
            }
            _append_journal({
                "type": "decision",
                "timestamp_utc": _utc_now_iso(),
                "instrument": instrument,
                "decision": out["decision"],
                "policy": out["policy"],
                "reasons": out["reasons"],
                "equity": round(current_equity, 6),
                "equity_peak": round(equity_peak, 6),
                "mode": self.mode,
            })
            return out

        # --------------------------------------------------
        # Daily loss cap (based on *daily start equity*)
        # --------------------------------------------------
        if state.get("daily_start_equity") is None:
            state["daily_start_equity"] = current_equity

        daily_start = float(state["daily_start_equity"])
        daily_floor = daily_start * (1.0 - float(self.policy.daily_loss_cap_pct))

        if state.get("daily_shutdown"):
            out = {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state.get("daily_shutdown_reason") or "Daily shutdown active"],
            }
            _append_journal({
                "type": "decision",
                "timestamp_utc": _utc_now_iso(),
                "instrument": instrument,
                "decision": out["decision"],
                "policy": out["policy"],
                "reasons": out["reasons"],
                "equity": round(current_equity, 6),
                "equity_peak": round(equity_peak, 6),
                "mode": self.mode,
            })
            return out

        if current_equity <= daily_floor:
            state["daily_shutdown"] = True
            state["daily_shutdown_reason"] = (
                f"DAILY LOSS CAP HIT: equity {current_equity:.2f} <= floor {daily_floor:.2f} "
                f"(cap={self.policy.daily_loss_cap_pct:.2%}, start={daily_start:.2f})"
            )
            out = {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [state["daily_shutdown_reason"]],
            }
            _append_journal({
                "type": "decision",
                "timestamp_utc": _utc_now_iso(),
                "instrument": instrument,
                "decision": out["decision"],
                "policy": out["policy"],
                "reasons": out["reasons"],
                "equity": round(current_equity, 6),
                "equity_peak": round(equity_peak, 6),
                "mode": self.mode,
            })
            return out

        # --------------------------------------------------
        # Cooldown enforcement
        # --------------------------------------------------
        cd = state.get("cooldown_until")
        if cd:
            try:
                if datetime.fromisoformat(str(cd)) > _utc_now():
                    out = {
                        "decision": BLOCK,
                        "policy": self.policy.name,
                        "reasons": ["Cooldown active"],
                    }
                    _append_journal({
                        "type": "decision",
                        "timestamp_utc": _utc_now_iso(),
                        "instrument": instrument,
                        "decision": out["decision"],
                        "policy": out["policy"],
                        "reasons": out["reasons"],
                        "equity": round(current_equity, 6),
                        "equity_peak": round(equity_peak, 6),
                        "mode": self.mode,
                    })
                    return out
                else:
                    state["cooldown_until"] = None
            except Exception:
                state["cooldown_until"] = None

        # --------------------------------------------------
        # Max trades/day
        # --------------------------------------------------
        if int(state.get("trades_today") or 0) >= int(self.policy.max_trades_per_day):
            out = {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [f"Max trades/day reached ({state.get('trades_today')}/{self.policy.max_trades_per_day})"],
            }
            _append_journal({
                "type": "decision",
                "timestamp_utc": _utc_now_iso(),
                "instrument": instrument,
                "decision": out["decision"],
                "policy": out["policy"],
                "reasons": out["reasons"],
                "equity": round(current_equity, 6),
                "equity_peak": round(equity_peak, 6),
                "mode": self.mode,
            })
            return out

        # --------------------------------------------------
        # Loss streak → cooldown
        # --------------------------------------------------
        if int(state.get("consecutive_losses") or 0) >= int(self.policy.max_consecutive_losses):
            state["cooldown_until"] = (_utc_now() + timedelta(minutes=self.policy.cooldown_minutes)).isoformat()
            out = {
                "decision": BLOCK,
                "policy": self.policy.name,
                "reasons": [f"Loss streak limit hit ({self.policy.max_consecutive_losses}/{self.policy.max_consecutive_losses}) → cooldown"],
            }
            _append_journal({
                "type": "decision",
                "timestamp_utc": _utc_now_iso(),
                "instrument": instrument,
                "decision": out["decision"],
                "policy": out["policy"],
                "reasons": out["reasons"],
                "equity": round(current_equity, 6),
                "equity_peak": round(equity_peak, 6),
                "mode": self.mode,
            })
            return out

        out = {
            "decision": ALLOW,
            "policy": self.policy.name,
            "reasons": ["approved"],
        }

        _append_journal({
            "type": "decision",
            "timestamp_utc": _utc_now_iso(),
            "instrument": instrument,
            "decision": out["decision"],
            "policy": out["policy"],
            "reasons": out["reasons"],
            "equity": round(current_equity, 6),
            "equity_peak": round(equity_peak, 6),
            "mode": self.mode,
        })

        return out
