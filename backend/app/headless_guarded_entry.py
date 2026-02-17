"""
backend/app/headless_guarded_entry.py
=====================================

Canonical Guarded Entry Layer
Capital Strata Systems

Bridges:
  run_live_guarded.py
  →
  ExecutionGate

Design:
- FAIL-CLOSED by default (no live)
- Tolerant to different ExecutionGate versions:
  - If sync_context exists, we call it
  - If not, we skip without crashing
"""

from __future__ import annotations

from typing import Any, Dict
from dataclasses import dataclass
from datetime import datetime, timezone

from engine.execution.execution_gate import ExecutionGate


# ============================================================
# Config
# ============================================================

@dataclass
class HeadlessConfig:
    allow_live: bool = False


# ============================================================
# Utilities
# ============================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Core Entrypoint
# ============================================================

def run_headless(req: Dict[str, Any], cfg: HeadlessConfig) -> Dict[str, Any]:
    """
    Guarded headless execution.

    This:
    - Builds ExecutionGate
    - Optionally syncs context (if supported by gate)
    - Evaluates trade (if trade fields exist)
    - Returns structured diagnostics
    """

    gate = ExecutionGate()

    symbol = req.get("fx_instrument") or req.get("symbol") or "EURUSD"

    # --------------------------------------------------------
    # Optional context injection (tolerant)
    # --------------------------------------------------------
    equity = req.get("equity")
    equity_peak = req.get("equity_peak")

    # Some builds include gate.sync_context(...). Some don't.
    sync_fn = getattr(gate, "sync_context", None)
    if callable(sync_fn):
        try:
            sync_fn(
                equity=equity,
                equity_peak=equity_peak,
            )
        except Exception:
            # Never crash guarded startup because of optional context sync
            pass

    # --------------------------------------------------------
    # Trade evaluation (probe-safe)
    # --------------------------------------------------------
    side = req.get("side")
    notional = req.get("notional")
    stop_pct = req.get("stop_distance_pct")

    # Optional diagnostics kwargs (ExecutionGate should tolerate extras)
    equity_risk = req.get("equity_risk")
    regime_persistence = req.get("regime_persistence")

    if side is not None and notional is not None and stop_pct is not None:
        decision = gate.evaluate_trade(
            instrument=symbol,
            side=side,
            notional=float(notional),
            stop_distance_pct=float(stop_pct),
            policy="core",
            equity_risk=equity_risk,
            regime_persistence=regime_persistence,
        )
    else:
        # Probe call: should return "missing_required_fields" instead of crashing
        decision = gate.evaluate_trade(
            instrument=symbol,
            policy="core",
            equity_risk=equity_risk,
            regime_persistence=regime_persistence,
        )

    # --------------------------------------------------------
    # Diagnostics envelope
    # --------------------------------------------------------
    return {
        "ok": True,
        "timestamp_utc": _utc_now(),
        "mode": "SIMULATION",
        "symbol": symbol,
        "steps_executed": 1,
        "gate_decision": decision,
    }
