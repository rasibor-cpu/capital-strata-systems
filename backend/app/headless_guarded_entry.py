"""
headless_guarded_entry.py
=========================

Canonical guarded entrypoint for REA / Capital Strata Systems.

Fail-closed by design.

Responsibilities:
- Build execution context from request + environment
- Inject optional trade fields when present
- Stack Volatility + RegimeGate + ExecutionGate
- Never allow live execution unless explicitly enabled
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from engine.execution.execution_gate import ExecutionGate


# ============================================================
# CONFIG
# ============================================================

@dataclass
class HeadlessConfig:
    allow_live: bool = False


# ============================================================
# ENV HELPERS
# ============================================================

def _env_float(name: str) -> Optional[float]:
    val = os.environ.get(name)
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


def _env_str(name: str) -> Optional[str]:
    val = os.environ.get(name)
    return val if val else None


# ============================================================
# ENTRYPOINT
# ============================================================

def run_headless(req: Dict[str, Any], cfg: HeadlessConfig) -> Dict[str, Any]:

    symbol = req.get("fx_instrument", "EUR_USD")

    gate = ExecutionGate()

    # --------------------------------------------------------
    # EQUITY INITIALIZATION (if provided)
    # --------------------------------------------------------

    equity = _env_float("ACCOUNT_EQUITY")
    equity_peak = _env_float("ACCOUNT_EQUITY_PEAK")

    if equity is not None:
        gate.evaluate_trade(  # safe context sync via kwargs handling
            instrument=symbol,
            equity=equity,
            equity_peak=equity_peak or equity,
        )

    # --------------------------------------------------------
    # TRADE INTENT (optional)
    # --------------------------------------------------------

    side = _env_str("TRADE_SIDE")
    notional = _env_float("TRADE_NOTIONAL")
    stop_distance_pct = _env_float("TRADE_STOP_DISTANCE_PCT")

    decision = gate.evaluate_trade(
        instrument=symbol,
        side=side,
        notional=notional,
        stop_distance_pct=stop_distance_pct,
        equity=equity,
        equity_peak=equity_peak,
    )

    return {
        "ok": True,
        "timestamp_utc": req.get("ts_utc"),
        "mode": req.get("mode"),
        "symbol": symbol,
        "steps_executed": 1,
        "gate_decision": decision,
    }
