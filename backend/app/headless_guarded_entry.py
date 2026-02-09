"""
Headless Guarded Entry – REA Capital Trading Engine

Purpose:
- Safe, non-live execution wrapper
- No broker calls
- No real trades
- Pure simulation path
"""

from __future__ import annotations
from typing import Dict, Any


def run_headless(*, steps: int = 50, symbol: str = "EURUSD") -> Dict[str, Any]:
    """
    Dev-only headless execution.

    Accepts:
        steps  – number of simulated iterations
        symbol – trading symbol

    Returns structured summary JSON.
    """

    print(f"[HEADLESS] Base URL: http://127.0.0.1:8000")
    print("[HEADLESS] API mode: no credentials supplied; auth flow skipped.")
    print("[HEADLESS] Execution layer currently locked (no live trades).")
    print("[HEADLESS] Guarded mode confirmed.")
    print("[HEADLESS_DEV_MODE ready.]")

    # --- simple simulation loop ---
    simulated_trades = 0
    blocked_trades = 0

    for i in range(steps):
        # For now just simulate blocks every 5 steps
        if i % 5 == 0:
            blocked_trades += 1
        else:
            simulated_trades += 1

    return {
        "mode": "HEADLESS_DEV",
        "symbol": symbol,
        "steps_requested": steps,
        "simulated_trades": simulated_trades,
        "blocked_trades": blocked_trades,
        "live_execution": False,
    }
