"""
backend/app/headless_guarded_entry.py

Phase 1 – Headless Guarded Entry
Aligned with engine.risk.risk_governor (RiskGovernor + apply_trade).

Fail-closed:
- Default execution is locked
- We evaluate a synthetic TradeRequest derived from the headless run request
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from engine.risk.risk_governor import RiskGovernor, apply_trade


# ---------------------------------------------------------
# Configuration (Phase 1)
# ---------------------------------------------------------

@dataclass
class HeadlessConfig:
    # NOTE: RiskGovernor has internal hard limits too.
    execution_locked: bool = True  # Fail-closed default


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _normalize_symbol(symbol: str) -> str:
    # Your RiskGovernor expects "instrument"
    return (symbol or "").strip() or "EURUSD"


def _mode(mode: str) -> str:
    return (mode or "SIMULATION").strip().upper()


def _coerce_stop_distance_pct(steps: int) -> float:
    """
    We need a stop_distance_pct for risk approximation.
    For Phase 1 headless we choose a safe, conservative default.

    Keep within RiskGovernor validation: (0, 0.25)
    """
    # Conservative fixed 1% stop distance approximation
    return 0.01


def _coerce_notional(steps: int) -> float:
    """
    Headless run doesn't currently carry notional.
    For Phase 1 we use a small deterministic notional that should usually pass caps
    (unless caps are intentionally very tight).
    """
    # Deterministic small notional for simulation
    return 1000.0


# ---------------------------------------------------------
# Entry
# ---------------------------------------------------------

def run_headless(
    *,
    steps: int,
    symbol: str,
    execution_mode: str,
    current_open_positions: int = 0,
    trades_today: int = 0,
    consecutive_losses: int = 0,
    current_equity: Optional[float] = None,
    peak_equity: Optional[float] = None,
    cfg: Optional[HeadlessConfig] = None,
) -> Dict[str, Any]:

    if cfg is None:
        cfg = HeadlessConfig()

    # -----------------------------
    # Build Governor (Phase 1 memory)
    # -----------------------------
    governor = RiskGovernor()

    # Hydrate governor state from request (Phase 1 emulation)
    # NOTE: RiskGovernor tracks equity, equity_peak, trades_today, consecutive_losses internally.
    if current_equity is not None:
        governor.update_equity(float(current_equity))
    if peak_equity is not None:
        # RiskGovernor updates peak internally only when equity exceeds peak,
        # so we directly set peak via internal state for Phase 1 compatibility.
        governor.state["equity_peak"] = float(peak_equity)

    governor.state["trades_today"] = int(trades_today)
    governor.state["consecutive_losses"] = int(consecutive_losses)

    # current_open_positions isn't modeled in RiskGovernor state yet.
    # We'll include it in the response for visibility only.
    # (If you later add position tracking, we can wire it in.)

    # -----------------------------
    # Convert Headless request -> TradeRequest dict
    # -----------------------------
    req_dict = {
        "instrument": _normalize_symbol(symbol),
        "side": "buy",  # Phase 1 default (doesn't matter for caps)
        "notional": _coerce_notional(steps),
        "stop_distance_pct": _coerce_stop_distance_pct(steps),
        "policy": "core",
    }

    # -----------------------------
    # Risk Decision
    # -----------------------------
    decision = apply_trade(governor, req_dict)  # returns dict with "ok", "reasons", "caps", "timestamp_utc"

    blocked = not bool(decision.get("ok", False))

    # -----------------------------
    # Fail-closed execution policy
    # -----------------------------
    exec_mode = _mode(execution_mode)
    execution_allowed = (not blocked) and (not cfg.execution_locked) and (exec_mode != "LIVE")

    return {
        "ok": execution_allowed,
        "blocked": blocked,
        "execution_locked": cfg.execution_locked,
        "execution_mode": exec_mode,
        "steps": int(steps),
        "symbol": _normalize_symbol(symbol),

        # visibility / debug
        "input_state": {
            "trades_today": int(trades_today),
            "consecutive_losses": int(consecutive_losses),
            "current_open_positions": int(current_open_positions),
            "current_equity": current_equity,
            "peak_equity": peak_equity,
        },
        "trade_request": req_dict,
        "risk_decision": decision,
        "note": "Phase 1 headless evaluation complete (RiskGovernor.allow_trade).",
    }
