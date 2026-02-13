"""
Phase 1 (Headless) guarded entrypoint
Capital Strata Systems / REA Capital Trading Engine

Fail-closed by design.
Stable callable surface for API.

Allowed signature:
    run_headless(req: dict, cfg: HeadlessConfig) -> dict
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any


# ----------------------------------------------------------
# Utilities
# ----------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------
# Config
# ----------------------------------------------------------

@dataclass
class HeadlessConfig:
    execution_locked: bool = True
    max_trades_per_day: int = 15
    max_positions: int = 20
    max_consecutive_losses: int = 5
    cooldown_seconds: int = 3600


# ----------------------------------------------------------
# Stable Entry Point
# ----------------------------------------------------------

def run_headless(req: dict, cfg: HeadlessConfig) -> dict:
    """
    Stable execution surface for Phase 1.

    Expected call pattern:
        run_headless(req: dict, cfg: HeadlessConfig)

    Fail-closed design.
    """

    try:
        if not isinstance(req, dict):
            raise TypeError("req must be dict")

        # Extract inputs safely
        steps = int(req.get("steps", 1))
        symbol = str(req.get("symbol", "EURUSD"))
        execution_mode = str(req.get("execution_mode", "SIMULATION"))

        current_open_positions = int(req.get("current_open_positions", 0))
        trades_today = int(req.get("trades_today", 0))
        consecutive_losses = int(req.get("consecutive_losses", 0))

        current_equity = float(req.get("current_equity", 100000.0))
        peak_equity = float(req.get("peak_equity", current_equity))

        # --------------------------------------------------
        # Lazy import to avoid circular imports
        # --------------------------------------------------
        from engine.risk.risk_governor import RiskGovernor

        governor = RiskGovernor()
        governor.update_equity(current_equity)

        # --------------------------------------------------
        # Fail-closed execution logic
        # --------------------------------------------------
        if execution_mode in {"LIVE", "PAPER"}:
            if cfg.execution_locked:
                return {
                    "ok": False,
                    "timestamp_utc": _utc_now_iso(),
                    "error": "Execution locked by configuration",
                }

        # --------------------------------------------------
        # Phase 1 simulated loop
        # --------------------------------------------------
        for _ in range(steps):
            # Placeholder for engine logic
            pass

        return {
            "ok": True,
            "timestamp_utc": _utc_now_iso(),
            "mode": execution_mode,
            "symbol": symbol,
            "steps_executed": steps,
        }

    except Exception as e:
        return {
            "ok": False,
            "timestamp_utc": _utc_now_iso(),
            "error": f"{type(e).__name__}: {str(e)}",
        }
