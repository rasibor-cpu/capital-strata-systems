"""
Phase 1 (Headless) guarded entrypoint
Capital Strata Systems / REA Capital Trading Engine

Clean architecture:
- No direct RiskGovernor imports
- All approval flows through ExecutionGate
- Fail-closed design
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any

# Runtime import only (prevents circular import)
from engine.execution.execution_gate import ExecutionGate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HeadlessConfig:
    execution_mode: str = "SIMULATION"


def run_headless(req: Dict[str, Any], cfg: HeadlessConfig) -> Dict[str, Any]:
    """
    Stable callable surface used by API wrapper.
    """

    symbol = req.get("symbol", "UNKNOWN")
    steps = int(req.get("steps", 1))
    current_equity = float(req.get("current_equity", 100000))

    if cfg.execution_mode != "SIMULATION":
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": "Non-SIMULATION mode blocked (fail-closed)."
        }

    # ---------------------------------------
    # 1️⃣  Instantiate Execution Gate
    # ---------------------------------------
    gate = ExecutionGate()

    # ---------------------------------------
    # 2️⃣  Ask for approval
    # ---------------------------------------
    decision = gate.evaluate_trade(
        instrument=symbol,
        equity_risk=0.005 * current_equity  # 0.5% simulated risk
    )

    if decision["status"] != "APPROVED":
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "mode": cfg.execution_mode,
            "symbol": symbol,
            "error": "TRADE_REJECTED",
            "risk": decision
        }

    # ---------------------------------------
    # 3️⃣  Simulated execution
    # ---------------------------------------
    return {
        "ok": True,
        "timestamp_utc": _utc_now_iso(),
        "mode": cfg.execution_mode,
        "symbol": symbol,
        "steps_executed": steps,
        "risk": decision
    }
