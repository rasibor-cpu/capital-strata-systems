"""
Headless Guarded Entry
Capital Strata Systems / REA Capital Trading Engine

Phase 1 – Clean Interface Alignment
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from engine.execution.execution_gate import ExecutionGate


# ----------------------------------------------------------
# Config Object
# ----------------------------------------------------------

@dataclass
class HeadlessConfig:
    allow_live: bool = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------
# Headless Runner
# ----------------------------------------------------------

def run_headless(req: Dict[str, Any], cfg: HeadlessConfig) -> Dict[str, Any]:

    symbol = req.get("symbol", "EURUSD")
    steps = int(req.get("steps", 1))
    mode = req.get("execution_mode", "SIMULATION")

    if mode != "SIMULATION" and not cfg.allow_live:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": "LIVE/PAPER mode blocked (fail-closed).",
        }

    gate = ExecutionGate()

    # Phase 1 simplified risk calculation
    equity = float(req.get("current_equity", 100000))
    risk_budget_pct = 0.005  # 0.5% default
    equity_risk = equity * risk_budget_pct

    decision = gate.evaluate_trade(
        instrument=symbol,
        equity_risk=equity_risk,
    )

    return {
        "ok": True,
        "timestamp_utc": _utc_now_iso(),
        "mode": mode,
        "symbol": symbol,
        "steps_executed": steps,
        "gate_decision": decision,
    }
